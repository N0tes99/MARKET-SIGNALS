import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function backendBase(): string {
  return (
    process.env.API_BACKEND_URL?.replace(/\/$/, "") ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
    "http://localhost:8000"
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
  const auth = authHeader();
  if (auth) {
    headers.set("authorization", auth);
  }

  // Stay under typical Netlify/serverless upstream limits; return 504 instead of hanging.
  const PROXY_TIMEOUT_MS = 50_000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

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
    const message = error instanceof Error ? error.message : "Upstream error";
    return NextResponse.json({ detail: message }, { status: 502 });
  } finally {
    clearTimeout(timer);
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
