"use client";

import { PropsWithChildren, useEffect, useState } from "react";

import { MsalProvider } from "@azure/msal-react";

import { getMsalInstance } from "@/auth/entra-auth";

const msalInstance = getMsalInstance();

export function EntraProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let mounted = true;

    const bootstrap = async () => {
      try {
        await msalInstance.initialize();
        const redirectResult = await msalInstance.handleRedirectPromise();

        const activeAccount = redirectResult?.account ?? msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];
        if (activeAccount) {
          msalInstance.setActiveAccount(activeAccount);
        }
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
