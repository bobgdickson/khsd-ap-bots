type DebugDetails = Record<string, unknown>;

const ENABLE_AUTH_DEBUG =
  process.env.NEXT_PUBLIC_AUTH_DEBUG === "1" ||
  process.env.NEXT_PUBLIC_AUTH_DEBUG?.toLowerCase() === "true";

const REDACTED = "[REDACTED]";
const REDACT_KEYS = ["token", "secret", "password", "assertion"];

function shouldRedact(key: string): boolean {
  const normalized = key.toLowerCase();
  return REDACT_KEYS.some((sensitiveKey) => normalized.includes(sensitiveKey));
}

function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeValue(item));
  }

  if (value && typeof value === "object") {
    const sanitizedEntries = Object.entries(value as Record<string, unknown>).map(([key, childValue]) => {
      if (shouldRedact(key)) {
        return [key, REDACTED];
      }
      return [key, sanitizeValue(childValue)];
    });
    return Object.fromEntries(sanitizedEntries);
  }

  if (typeof value === "string" && value.length > 500) {
    return `${value.slice(0, 500)}...[truncated]`;
  }

  return value;
}

export function toErrorDetails(error: unknown): DebugDetails {
  if (error instanceof Error) {
    const enrichedError = error as Error & {
      errorCode?: string;
      subError?: string;
      correlationId?: string;
      traceId?: string;
      timestamp?: string;
    };

    return {
      name: enrichedError.name,
      message: enrichedError.message,
      errorCode: enrichedError.errorCode,
      subError: enrichedError.subError,
      correlationId: enrichedError.correlationId,
      traceId: enrichedError.traceId,
      timestamp: enrichedError.timestamp,
      stack: enrichedError.stack,
    };
  }

  if (typeof error === "string") {
    return { message: error };
  }

  if (error && typeof error === "object") {
    return { ...((error as Record<string, unknown>) ?? {}) };
  }

  return { message: String(error) };
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "Unknown error";
}

export async function authDebugLog(event: string, details: DebugDetails = {}): Promise<void> {
  if (!ENABLE_AUTH_DEBUG) {
    return;
  }

  const payload = {
    event,
    details: sanitizeValue(details),
    timestamp: new Date().toISOString(),
  };

  console.info("[auth-debug]", payload);

  try {
    await fetch("/api/auth-debug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch (error) {
    console.warn("[auth-debug] failed to send debug log to server", toErrorDetails(error));
  }
}
