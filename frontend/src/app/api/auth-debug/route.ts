import { NextRequest, NextResponse } from "next/server";

const ENABLE_AUTH_DEBUG =
  process.env.NEXT_PUBLIC_AUTH_DEBUG === "1" ||
  process.env.NEXT_PUBLIC_AUTH_DEBUG?.toLowerCase() === "true";

export async function POST(request: NextRequest) {
  if (!ENABLE_AUTH_DEBUG) {
    return NextResponse.json({ ok: false }, { status: 404 });
  }

  const body = await request.json().catch(() => ({ event: "invalid_json", details: {} }));
  const { event, details, timestamp } = body as {
    event?: string;
    details?: Record<string, unknown>;
    timestamp?: string;
  };

  console.log("[auth-debug][server]", {
    timestamp: timestamp ?? new Date().toISOString(),
    event: event ?? "unknown_event",
    details: details ?? {},
  });

  return NextResponse.json({ ok: true });
}
