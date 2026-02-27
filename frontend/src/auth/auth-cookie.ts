export const AUTH_COOKIE_NAME = "khsd_auth";
const AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 8;

function secureCookieSuffix(): string {
  if (typeof window !== "undefined" && window.location.protocol === "https:") {
    return "; Secure";
  }
  return "";
}

export function setAuthCookie() {
  if (typeof document === "undefined") {
    return;
  }
  document.cookie = `${AUTH_COOKIE_NAME}=1; Path=/; Max-Age=${AUTH_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax${secureCookieSuffix()}`;
}

export function clearAuthCookie() {
  if (typeof document === "undefined") {
    return;
  }
  document.cookie = `${AUTH_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secureCookieSuffix()}`;
}
