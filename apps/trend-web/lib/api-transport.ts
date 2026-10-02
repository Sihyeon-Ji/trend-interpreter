const METADATA_IDENTITY = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
const TOKEN_REFRESH_MARGIN_MS = 60_000;
const METADATA_TIMEOUT_MS = 3_000;

export type ApiRequestInit = RequestInit & { next?: { revalidate?: number | false; tags?: string[] } };
type Fetcher = (url: string, init?: ApiRequestInit) => Promise<Response>;

async function waitForToken(pending: Promise<string>, signal?: AbortSignal | null): Promise<string> {
  if (!signal) return pending;
  signal.throwIfAborted();
  let onAbort: () => void = () => {};
  const cancelled = new Promise<never>((_, reject) => {
    onAbort = () => reject(signal.reason);
    signal.addEventListener("abort", onAbort, { once: true });
  });
  try {
    return await Promise.race([pending, cancelled]);
  } finally {
    signal.removeEventListener("abort", onAbort);
  }
}

export function createApiTransport(baseUrl: string, auth: string, cloudRun: boolean, fetcher: Fetcher = fetch) {
  const base = new URL(baseUrl);
  if (base.username || base.password || base.search || base.hash || base.pathname !== "/") {
    throw new Error("TREND_API_URL must be an origin");
  }
  if (!["none", "google-id-token"].includes(auth) || (cloudRun && auth !== "google-id-token")) {
    throw new Error("Cloud Run API authentication is not configured");
  }
  if (!["http:", "https:"].includes(base.protocol) ||
      (auth === "google-id-token" && (base.protocol !== "https:" || base.port !== "" || !base.hostname.endsWith(".run.app")))) {
    throw new Error("Invalid API origin for authentication mode");
  }
  const audience = base.origin;
  let cached: { token: string; expiresAt: number } | undefined;
  let refreshing: Promise<string> | undefined;

  async function acquireToken(): Promise<string> {
    try {
      const url = new URL(METADATA_IDENTITY);
      url.searchParams.set("audience", audience);
      const response = await fetcher(url.toString(), {
        headers: { "Metadata-Flavor": "Google" }, cache: "no-store", redirect: "error",
        signal: AbortSignal.timeout(METADATA_TIMEOUT_MS),
      });
      if (!response.ok || response.headers.get("Metadata-Flavor") !== "Google") throw new Error();
      const token = (await response.text()).trim();
      const parts = token.split(".");
      if (parts.length !== 3 || parts.some((part) => !/^[A-Za-z0-9_-]+$/.test(part))) throw new Error();
      // Metadata is the trusted issuer; Cloud Run verifies the signature. Decode only to cache safely.
      const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8")) as { aud?: string; exp?: number };
      if (claims.aud !== audience || !Number.isSafeInteger(claims.exp) ||
          claims.exp! * 1000 <= Date.now() + TOKEN_REFRESH_MARGIN_MS) throw new Error();
      cached = { token, expiresAt: claims.exp! * 1000 };
      return token;
    } catch {
      throw new Error("API identity token unavailable");
    }
  }

  function identityToken(): Promise<string> {
    if (cached && cached.expiresAt > Date.now() + TOKEN_REFRESH_MARGIN_MS) return Promise.resolve(cached.token);
    if (!refreshing) refreshing = acquireToken().finally(() => { refreshing = undefined; });
    return refreshing;
  }

  return async function apiFetch(path: string, init: ApiRequestInit = {}): Promise<Response> {
    if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) throw new Error("Invalid API path");
    const url = new URL(path, base);
    if (url.origin !== audience) throw new Error("API origin mismatch");
    init.signal?.throwIfAborted();
    const headers = new Headers(init.headers);
    headers.delete("x-serverless-authorization");
    if (auth === "google-id-token") {
      const token = await waitForToken(identityToken(), init.signal);
      init.signal?.throwIfAborted();
      headers.set("X-Serverless-Authorization", `Bearer ${token}`);
    }
    return fetcher(url.toString(), { ...init, headers, redirect: "error" });
  };
}
