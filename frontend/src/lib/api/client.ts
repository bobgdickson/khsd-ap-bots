import OpenAPIClientAxios from "openapi-client-axios";

export const baseUrl =
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const apiKey = process.env.API_KEY ?? process.env.NEXT_PUBLIC_API_KEY;

const openapi = new OpenAPIClientAxios({
  definition: `${baseUrl}/openapi.json`,
  axiosConfigDefaults: {
    baseURL: baseUrl,
    headers: {
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
    },
  },
});

export const apiClient = await openapi.init();
export const apiSpec = await openapi.definition; // full OpenAPI JSON

/**
 * Dynamic fetch: no static schema or codegen required.
 */
export async function loadApiData<T = any>(path: string): Promise<T[]> {
  const response = await apiClient.get(path);
  return Array.isArray(response.data) ? response.data : [];
}

/**
 * Optional: look up field definitions dynamically from the OpenAPI spec.
 */

function isResponseObject(obj: any): obj is { content?: Record<string, any> } {
  return !!obj && typeof obj === "object" && "content" in obj;
}

export function getSchemaFor(path: string, method: "get" | "post" = "get") {
  const op = (apiSpec.paths?.[path] ?? {})[method];
  const resp = op?.responses?.["200"];
  const schema = isResponseObject(resp) ? resp.content?.["application/json"]?.schema : undefined;
  return schema;
}
