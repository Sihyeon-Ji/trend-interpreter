import "server-only";
import { createApiTransport, type ApiRequestInit } from "./api-transport";

let transport: ReturnType<typeof createApiTransport> | undefined;

export function apiFetch(path: string, init?: ApiRequestInit): Promise<Response> {
  transport ??= createApiTransport(
    process.env.TREND_API_URL ?? "http://localhost:8080",
    process.env.TREND_API_AUTH ?? "none",
    Boolean(process.env.K_SERVICE),
  );
  return transport(path, init);
}
