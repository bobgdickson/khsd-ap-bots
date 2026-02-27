"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

import { InteractionStatus } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import { clearAuthCookie, setAuthCookie } from "@/auth/auth-cookie";

export function DashboardAuthGuard() {
  const router = useRouter();
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  useEffect(() => {
    if (inProgress !== InteractionStatus.None) {
      return;
    }

    if (!isAuthenticated) {
      clearAuthCookie();
      router.replace("/auth/v2/login");
      return;
    }

    const account = instance.getActiveAccount() ?? accounts.at(0);
    if (account) {
      instance.setActiveAccount(account);
      setAuthCookie();
    }
  }, [accounts, inProgress, instance, isAuthenticated, router]);

  return null;
}
