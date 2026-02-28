"use client";

import { PropsWithChildren, useEffect, useState } from "react";

import type { AuthenticationResult } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";

import { authDebugLog, toErrorDetails } from "@/auth/debug-log";
import { getMsalInstance } from "@/auth/entra-auth";

const msalInstance = getMsalInstance();

function getCandidateAccount(redirectResult: AuthenticationResult | null) {
  return redirectResult?.account ?? msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];
}

async function setAndLogActiveAccount(redirectResult: AuthenticationResult | null) {
  const activeAccount = getCandidateAccount(redirectResult);
  if (!activeAccount) {
    return;
  }

  msalInstance.setActiveAccount(activeAccount);
  await authDebugLog("provider.active_account_set", {
    username: activeAccount.username,
    tenantId: activeAccount.tenantId,
    homeAccountId: activeAccount.homeAccountId,
  });
}

async function bootstrapMsal() {
  await authDebugLog("provider.bootstrap_start");
  await msalInstance.initialize();
  await authDebugLog("provider.initialized");

  const redirectResult = await msalInstance.handleRedirectPromise();
  await authDebugLog("provider.redirect_result", {
    hasRedirectResult: Boolean(redirectResult),
    accountUsername: redirectResult?.account?.username,
    accountTenant: redirectResult?.account?.tenantId,
  });

  await setAndLogActiveAccount(redirectResult);
}

export function EntraProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let mounted = true;

    const bootstrap = async () => {
      try {
        await bootstrapMsal();
      } catch (error) {
        await authDebugLog("provider.bootstrap_error", toErrorDetails(error));
      } finally {
        if (mounted) {
          setReady(true);
        }
      }
    };

    void bootstrap();

    return () => {
      mounted = false;
    };
  }, []);

  if (!ready) {
    return null;
  }

  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}
