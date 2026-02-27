import { Configuration, PublicClientApplication, RedirectRequest } from "@azure/msal-browser";

const tenantId = process.env.NEXT_PUBLIC_ENTRA_TENANT_ID;
const clientId = process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID;
const apiScope = process.env.NEXT_PUBLIC_ENTRA_API_SCOPE;

const redirectPath = process.env.NEXT_PUBLIC_ENTRA_REDIRECT_PATH ?? "/auth/v2/login";
const postLogoutRedirectPath = process.env.NEXT_PUBLIC_ENTRA_POST_LOGOUT_REDIRECT_PATH ?? "/auth/v2/login";
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

if (!tenantId) {
  throw new Error("Missing NEXT_PUBLIC_ENTRA_TENANT_ID");
}
if (!clientId) {
  throw new Error("Missing NEXT_PUBLIC_ENTRA_CLIENT_ID");
}
if (!apiScope) {
  throw new Error("Missing NEXT_PUBLIC_ENTRA_API_SCOPE");
}

function absoluteUrl(path: string): string {
  if (typeof window === "undefined") {
    return path;
  }
  return new URL(path, window.location.origin).toString();
}

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: absoluteUrl(redirectPath),
    postLogoutRedirectUri: absoluteUrl(postLogoutRedirectPath),
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

let msalInstance: PublicClientApplication | null = null;

export function getMsalInstance(): PublicClientApplication {
  msalInstance ??= new PublicClientApplication(msalConfig);
  return msalInstance;
}

const baseScopes = ["openid", "profile", "email"];

export const loginRequest: RedirectRequest = {
  scopes: [...baseScopes, apiScope],
};

export const apiTokenScopes = [apiScope];

export function getApiBaseUrl(): string {
  return apiBaseUrl.replace(/\/+$/, "");
}
