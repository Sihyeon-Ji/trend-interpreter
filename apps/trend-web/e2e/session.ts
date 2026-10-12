import { createHmac } from "node:crypto";

/* 서명된 세션 쿠키(lib/session.ts 와 같은 모양) — 개발 서버와 같은 SESSION_SECRET 을 PLAYWRIGHT_SESSION_SECRET 으로 받는다. */
export const secret = process.env.PLAYWRIGHT_SESSION_SECRET;
const b64 = (b: Buffer | string) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

export function sessionCookie(user: string, reviewer: boolean, readOnly = false) {
  const payload = b64(JSON.stringify({ u: user, r: reviewer, ...(readOnly ? { ro: true } : {}), exp: Math.floor(Date.now() / 1000) + 3600 }));
  return `${payload}.${b64(createHmac("sha256", secret!).update(payload).digest())}`;
}
