import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function backendBase(): string {
  return (
    process.env.API_BACKEND_URL?.replace(/\/$/, "") ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

function authHeader(): string | null {
  const user = process.env.API_USERNAME?.trim();
  const password = process.env.API_PASSWORD ?? "";
  if (!user || !password) {
    return null;
  }
  const token = Buffer.from(`${user}:${password}`, "utf8").toString("base64");
  return `Basic ${token}`;
}

function proxyTimeoutMs(targetPath: string): number {
  const normalized = targetPath.replace(/\/$/, "");
  if (normalized === "api/v1/chart-analysis") return 180_000;
  if (normalized === "api/v1/runners/backtest" || normalized === "api/v1/runners/tune") {
    return 180_000;
  }
  if (normalized.endsWith("/analysis")) return 90_000;
  if (normalized.startsWith("api/v1/expansion") || normalized.startsWith("api/v1/cortex")) {
    return 100_000;
  }
  const longRunning = new Set([
    "api/v1/assets",
    "api/v1/runners",
    "api/v1/runners/lists",
    "api/v1/runners/crypto",
    "api/v1/options-tape",
    "api/v1/perps/board",
    "api/v1/futures/board",
  ]);
  return longRunning.has(normalized) ? 100_000 : 50_000;
}

function forwardSetCookies(upstream: Response, responseHeaders: Headers): void {
  const getSetCookie = (
    upstream.headers as Headers & { getSetCookie?: () => string[] }
  ).getSetCookie;
  if (typeof getSetCookie === "function") {
    for (const cookie of getSetCookie.call(upstream.headers)) {
      responseHeaders.append("set-cookie", cookie);
    }
    return;
  }
  const single = upstream.headers.get("set-cookie");
  if (single) {
    responseHeaders.append("set-cookie", single);
  }
}

async function proxyRequest(
  request: NextRequest,
  pathSegments: string[],
): Promise<NextResponse> {
  const targetPath = pathSegments.join("/");
  const url = `${backendBase()}/${targetPath}${request.nextUrl.search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  const cookie = request.headers.get("cookie");
  if (cookie) {
    headers.set("cookie", cookie);
  }
  // Trust only Netlify's connection IP. Client-supplied XFF / X-Real-IP
  // would let an attacker pick their own rate-limit bucket.
  const clientIp = request.headers.get("x-nf-client-connection-ip")?.trim() || "";
  if (clientIp) {
    headers.set("x-forwarded-for", clientIp);
    headers.set("x-real-ip", clientIp);
  }
  // Do not forward X-Cron-Secret from the browser. Keep-warm hits Render
  // directly; a leaked cron secret must not work through the public site.
  const auth = authHeader();
  if (auth) {
    headers.set("authorization", auth);
  }

  // Cold /assets, Radar, Tape, Expansion, and Cortex often need 50–90s.
  // Default stays short so other routes fail fast; these get a longer budget
  // so Netlify does not 504 mid-compute when keep-warm has not run yet.
  const PROXY_TIMEOUT_MS = proxyTimeoutMs(targetPath);
  const isSse = targetPath.replace(/\/$/, "").startsWith("api/v1/sse");
  const controller = new AbortController();
  const timer = isSse
    ? null
    : setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
    signal: controller.signal,
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(url, init);
    const responseHeaders = new Headers();
    const upstreamType = upstream.headers.get("content-type");
    if (upstreamType) {
      responseHeaders.set("content-type", upstreamType);
    }
    forwardSetCookies(upstream, responseHeaders);

    if (isSse && upstream.body) {
      responseHeaders.set("cache-control", "no-cache");
      responseHeaders.set("connection", "keep-alive");
      responseHeaders.set("x-accel-buffering", "no");
      return new NextResponse(upstream.body, {
        status: upstream.status,
        headers: responseHeaders,
      });
    }

    // Response/NextResponse reject a body on 204/205/304.
    if (
      upstream.status === 204 ||
      upstream.status === 205 ||
      upstream.status === 304
    ) {
      return new NextResponse(null, {
        status: upstream.status,
        headers: responseHeaders,
      });
    }

    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const aborted =
      (error instanceof Error && error.name === "AbortError") ||
      (typeof DOMException !== "undefined" &&
        error instanceof DOMException &&
        error.name === "AbortError");
    if (aborted) {
      return NextResponse.json(
        {
          detail:
            "Upstream API timed out. Render free-tier cold starts or a full assets recompute can exceed the proxy limit — retry shortly.",
        },
        { status: 504 },
      );
    }
    // Log the real cause server-side only; the raw message can leak internal
    // connection details about API_BACKEND_URL to the client.
    const detail = error instanceof Error ? error.message : "Upstream error";
    console.error(`[api-proxy] upstream request failed: ${detail}`);
    return NextResponse.json(
      { detail: "Upstream API request failed. Please retry shortly." },
      { status: 502 },
    );
  } finally {
    if (timer) clearTimeout(timer);
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyRequest(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyRequest(request, path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyRequest(request, path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyRequest(request, path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyRequest(request, path);
}
