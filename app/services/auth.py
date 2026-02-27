"""
Entra ID (Azure AD) Authentication
Validates JWT tokens and loads permissions from database
"""

import logging
from functools import lru_cache
from typing import Any, cast

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)

class TokenValidationError(Exception):
    """Custom exception for token validation failures"""
    pass


def _tenant_id() -> str:
    tenant_id = settings.azure_tenant_id
    if not tenant_id:
        raise TokenValidationError("AZURE_TENANT_ID is not configured")
    return tenant_id


@lru_cache
def get_jwks_client() -> PyJWKClient:
    """Get cached JWKS client for token verification"""
    tenant_id = _tenant_id()
    jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    return PyJWKClient(jwks_url)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token from Entra ID

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        TokenValidationError: If token is invalid
    """
    try:
        # Get the signing key from Microsoft's JWKS endpoint
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Build list of valid audiences (filter out None values)
        audiences: list[str] = []
        if settings.azure_client_id:
            audiences.append(settings.azure_client_id)
        if settings.azure_api_uri:
            audiences.append(settings.azure_api_uri)
        if not audiences:
            raise TokenValidationError("Configure AZURE_CLIENT_ID and/or AZURE_API_URI")

        tenant_id = _tenant_id()
        issuers = [
            f"https://sts.windows.net/{tenant_id}/",
            f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        ]

        # Decode and validate the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=issuers,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        return cast(dict[str, Any], payload)

    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise TokenValidationError("Token has expired")
    except jwt.InvalidAudienceError:
        logger.warning("Invalid token audience")
        raise TokenValidationError("Invalid token audience")
    except jwt.InvalidIssuerError:
        logger.warning("Invalid token issuer")
        raise TokenValidationError("Invalid token issuer")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise TokenValidationError("Invalid token")
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise TokenValidationError("Token validation failed")


class User:
    """Represents an authenticated user"""

    def __init__(self, token_payload: dict[str, Any]):
        self.id = token_payload.get("oid")  # Object ID
        self.email = (
            token_payload.get("preferred_username") or
            token_payload.get("email") or
            token_payload.get("upn")
        )
        self.name = token_payload.get("name")
        self.roles = token_payload.get("roles", [])
        self.raw_claims = token_payload

        # Extended attributes from token (may need Graph API for full data)
        self.company_name: str | None = token_payload.get("company")
        self.department: str | None = token_payload.get("department")
        self.job_title: str | None = token_payload.get("jobTitle")

        # Permissions will be loaded from database
        self._permissions: dict[str, Any] | None = None

    @property
    def permissions(self) -> dict[str, Any] | None:
        """Get user's permissions"""
        return self._permissions

    @permissions.setter
    def permissions(self, value: Any):
        """
        Set user's permissions.

        Accepts either a dict or a UserPermissions dataclass object.
        UserPermissions objects are converted to dict for storage.
        """
        if value is None:
            self._permissions = None
        elif isinstance(value, dict):
            self._permissions = value
        elif hasattr(value, '__dataclass_fields__'):
            # Convert dataclass (UserPermissions) to dict
            from dataclasses import asdict
            self._permissions = asdict(value)
            # Convert set to list for JSON serialization
            if 'features' in self._permissions and isinstance(self._permissions['features'], set):
                self._permissions['features'] = list(self._permissions['features'])
        else:
            # Try to use object attributes as dict
            self._permissions = {
                'user_id': getattr(value, 'user_id', None),
                'email': getattr(value, 'email', None),
                'name': getattr(value, 'name', None),
                'department': getattr(value, 'department', None),
                'job_title': getattr(value, 'job_title', None),
                'company_name': getattr(value, 'company_name', None),
                'features': list(getattr(value, 'features', set())),
                'site_scope': getattr(value, 'site_scope', 'none'),
                'allowed_sites': getattr(value, 'allowed_sites', []),
                'is_it_department': getattr(value, 'is_it_department', False),
                'is_admin': getattr(value, 'is_admin', False),
            }

    def set_permissions(self, permissions: dict[str, Any]):
        """Set permissions loaded from database (deprecated, use property setter)"""
        self._permissions = permissions

    def has_feature(self, feature: str) -> bool:
        """Check if user has access to a feature"""
        if not self._permissions:
            return False
        return feature in self._permissions.get("features", [])

    def can_access_site(self, site_name: str) -> bool:
        """Check if user can access a site"""
        if not self._permissions:
            return False

        site_scope = self._permissions.get("site_scope", "none")
        if site_scope == "all":
            return True
        if site_scope == "none":
            return False

        allowed_sites = self._permissions.get("allowed_sites", [])
        for site in allowed_sites:
            if (site["short_code"].lower() in site_name.lower() or
                site["name"].lower() in site_name.lower()):
                return True
        return False

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        if self._permissions:
            return bool(self._permissions.get("is_admin", False))
        return "Admin" in self.roles

    @property
    def is_it_department(self) -> bool:
        """Check if user is in IT department"""
        if self._permissions:
            return bool(self._permissions.get("is_it_department", False))
        return bool(self.department and "information technology" in self.department.lower())

    def __repr__(self):
        return f"User(email={self.email}, name={self.name}, department={self.department})"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> User:
    """
    Dependency to get the current authenticated user

    Note: This returns the user with token claims only.
    Use get_current_user_with_permissions for full permissions from DB.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        user = User(payload)

        # Block substitute teachers from accessing the portal
        # Substitutes have company_name = "Kern County High School District"
        if user.company_name and user.company_name.lower() == "kern county high school district":
            logger.warning(f"Access denied for substitute teacher: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: This portal is not available for substitute teachers",
            )

        logger.info(f"Authenticated user: {user.email}")
        return user

    except TokenValidationError as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> User | None:
    """
    Dependency to get the current user if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
        return User(payload)
    except TokenValidationError:
        return None


def require_feature(feature: str):
    """
    Dependency factory to require a specific feature

    Usage:
        @app.get("/catalyst/devices")
        async def get_devices(
            user: User = Depends(get_current_user_with_permissions),
            _: None = Depends(require_feature("catalyst:devices"))
        ):
            ...
    """
    async def feature_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {feature} permission required"
            )
        return user

    return feature_checker
