"use client";

import { ReactNode } from "react";

import { Auth0Provider as BaseAuth0Provider } from "@auth0/nextjs-auth0";
import type { User } from "@auth0/nextjs-auth0/types";

interface Auth0ProviderProps {
  children: ReactNode;
  user?: User;
}

export function Auth0Provider({ children, user }: Auth0ProviderProps) {
  return <BaseAuth0Provider user={user}>{children}</BaseAuth0Provider>;
}
