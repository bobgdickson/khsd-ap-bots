import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";

import { authDebugLog, toErrorDetails } from "@/auth/debug-log";
import { apiTokenScopes, getApiBaseUrl } from "@/auth/entra-auth";

export async function getApiAccessToken(
  instance: IPublicClientApplication,
  account: AccountInfo,
): Promise<string> {
  await authDebugLog("api.acquire_token_silent_start", {
    username: account.username,
    scopes: apiTokenScopes,
  });

  try {
    const token = await instance.acquireTokenSilent({
      account,
      scopes: apiTokenScopes,
    });

    await authDebugLog("api.acquire_token_silent_success", {
      username: account.username,
      scopes: apiTokenScopes,
      expiresOn: token.expiresOn?.toISOString(),
    });

    return token.accessToken;
  } catch (error) {
    await authDebugLog("api.acquire_token_silent_error", toErrorDetails(error));
    throw error;
  }
}

export async function fetchApiMe(instance: IPublicClientApplication, account: AccountInfo): Promise<Response> {
  const accessToken = await getApiAccessToken(instance, account);

  const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  await authDebugLog("api.auth_me_response", {
    status: response.status,
    ok: response.ok,
    apiBaseUrl: getApiBaseUrl(),
  });

  return response;
}
