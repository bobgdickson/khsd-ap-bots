from fastapi import APIRouter, Depends

from ..services.auth import User, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "roles": user.roles,
        "department": user.department,
        "job_title": user.job_title,
        "company_name": user.company_name,
    }
