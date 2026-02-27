import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";

import { apiTokenScopes, getApiBaseUrl } from "@/auth/entra-auth";

export async function getApiAccessToken(
  instance: IPublicClientApplication,
  account: AccountInfo,
): Promise<string> {
  const token = await instance.acquireTokenSilent({
    account,
    scopes: apiTokenScopes,
  });
  return token.accessToken;
}

export async function fetchApiMe(instance: IPublicClientApplication, account: AccountInfo): Promise<Response> {
  const accessToken = await getApiAccessToken(instance, account);
  return fetch(`${getApiBaseUrl()}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}
