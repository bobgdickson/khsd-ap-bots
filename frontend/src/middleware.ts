import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "khsd_auth";
const DASHBOARD_PREFIX = "/dashboard";
const LOGIN_PATH = "/auth/v2/login";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isLoggedIn = request.cookies.get(AUTH_COOKIE_NAME)?.value === "1";

  if (!isLoggedIn && pathname.startsWith(DASHBOARD_PREFIX)) {
    const loginUrl = new URL(LOGIN_PATH, request.url);
    loginUrl.searchParams.set("returnTo", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (isLoggedIn && pathname === LOGIN_PATH) {
    return NextResponse.redirect(new URL("/dashboard/bots", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)"],
};
