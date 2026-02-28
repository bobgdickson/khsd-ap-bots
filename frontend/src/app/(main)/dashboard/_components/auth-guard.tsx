"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

import { InteractionStatus } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import { clearAuthCookie, setAuthCookie } from "@/auth/auth-cookie";
import { authDebugLog } from "@/auth/debug-log";

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
      void authDebugLog("dashboard.guard_unauthenticated");
      router.replace("/auth/v2/login");
      return;
    }

    const account = instance.getActiveAccount() ?? accounts.at(0);
    if (account) {
      instance.setActiveAccount(account);
      setAuthCookie();
      void authDebugLog("dashboard.guard_authenticated", {
        username: account.username,
        tenantId: account.tenantId,
      });
    }
  }, [accounts, inProgress, instance, isAuthenticated, router]);

  return null;
}
