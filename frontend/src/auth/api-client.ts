import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";

import { getErrorMessage } from "@/auth/debug-log";
import { getApiAccessToken } from "@/auth/entra-api";
import { getApiBaseUrl } from "@/auth/entra-auth";

function joinApiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

export function getActiveAccount(
  instance: IPublicClientApplication,
  accounts: AccountInfo[],
): AccountInfo | null {
  return instance.getActiveAccount() ?? accounts.at(0) ?? null;
}

export async function authFetch(
  instance: IPublicClientApplication,
  account: AccountInfo,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const accessToken = await getApiAccessToken(instance, account);
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(joinApiUrl(path), {
    ...init,
    headers,
  });
}

export async function authFetchJson<T>(
  instance: IPublicClientApplication,
  account: AccountInfo,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await authFetch(instance, account, path, init);
  if (!response.ok) {
    const responseText = await response.text().catch(() => "");
    throw new Error(
      `API request failed (${response.status} ${response.statusText}) ${responseText || getErrorMessage(response.statusText)}`,
    );
  }

  return response.json() as Promise<T>;
}
