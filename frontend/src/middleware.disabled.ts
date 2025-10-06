import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "./lib/auth0";

export async function middleware(request: NextRequest) {
  console.log("[middleware] fired:", request.nextUrl.pathname);

  const session = await auth0.getSession(request);
  // Example: protect anything under /dashboard
  if (request.nextUrl.pathname.startsWith("/dashboard") && !session) {
    const loginUrl = new URL("/auth/login", request.url);
    loginUrl.searchParams.set("returnTo", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  // otherwise let Auth0 handle /auth/* routes
  return auth0.middleware(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)"],
};
