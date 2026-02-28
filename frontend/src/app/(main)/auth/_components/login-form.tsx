"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { InteractionStatus } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { setAuthCookie } from "@/auth/auth-cookie";
import { authDebugLog, getErrorMessage, toErrorDetails } from "@/auth/debug-log";
import { fetchApiMe } from "@/auth/entra-api";
import { loginRequest } from "@/auth/entra-auth";
import { Button } from "@/components/ui/button";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = useMemo(() => searchParams.get("returnTo") ?? "/dashboard/bots", [searchParams]);

  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSyncingRef = useRef(false);

  useEffect(() => {
    if (inProgress !== InteractionStatus.None || !isAuthenticated || isSyncingRef.current) {
      return;
    }

    const account = instance.getActiveAccount() ?? accounts.at(0);
    if (!account) {
      void authDebugLog("login.sync_skipped_no_account");
      return;
    }

    isSyncingRef.current = true;

    const syncApiSession = async () => {
      try {
        await authDebugLog("login.sync_start", {
          username: account.username,
          tenantId: account.tenantId,
          returnTo,
        });
        instance.setActiveAccount(account);
        const meResponse = await fetchApiMe(instance, account);
        if (!meResponse.ok) {
          throw new Error(`API auth check failed (${meResponse.status})`);
        }
        setAuthCookie();
        await authDebugLog("login.sync_success", { returnTo });
        router.replace(returnTo);
      } catch (error) {
        isSyncingRef.current = false;
        setIsSubmitting(false);
        await authDebugLog("login.sync_error", toErrorDetails(error));
        toast.error(`Microsoft login worked, but API auth failed: ${getErrorMessage(error)}`);
      }
    };

    void syncApiSession();
  }, [accounts, inProgress, instance, isAuthenticated, returnTo, router]);

  const handleMicrosoftLogin = async () => {
    setIsSubmitting(true);
    try {
      await authDebugLog("login.redirect_start", {
        scopes: loginRequest.scopes,
        authority: instance.getConfiguration().auth.authority,
        redirectUri: instance.getConfiguration().auth.redirectUri,
      });
      await instance.loginRedirect(loginRequest);
    } catch (error) {
      setIsSubmitting(false);
      await authDebugLog("login.redirect_error", toErrorDetails(error));
      toast.error(`Unable to start Microsoft sign-in: ${getErrorMessage(error)}`);
    }
  };

  const isBusy = isSubmitting || inProgress !== InteractionStatus.None;

  return (
    <div className="space-y-4">
      <Button className="w-full" type="button" onClick={handleMicrosoftLogin} disabled={isBusy}>
        {isBusy ? (
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Signing in...
          </span>
        ) : (
          "Sign in with Microsoft"
        )}
      </Button>
      <p className="text-muted-foreground text-center text-xs">
        Use your KHSD Microsoft account. Access is validated against the API after sign-in.
      </p>
    </div>
  );
}
