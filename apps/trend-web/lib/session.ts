/** 로그인 세션 쿠키. 로그인한 사람은 설정을 갖고, 그중 검수자(r)만 /admin 에 들어간다.
 *   Edge 미들웨어에서도 검증해야 해서 Web Crypto(HMAC-SHA256)만 쓴다.
 *  형식: <payload>.<서명>  — payload 는 {"u":이름,"exp":만료초} 를 base64url 로.
 *  비밀값 SESSION_SECRET 은 서버 전용 환경변수다(NEXT_PUBLIC_ 아님 → 브라우저에 나가지 않는다). */

export const SESSION_COOKIE = "admin_session";
export const SESSION_HOURS = 12;

export type Session = { user: string; reviewer: boolean; readOnly: boolean; exp: number };

const enc = new TextEncoder();

function b64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function unb64url(s: string): Uint8Array<ArrayBuffer> {
  // ArrayBuffer 를 명시해야 Web Crypto 의 BufferSource 로 그대로 넘길 수 있다 (TS 5.7 의 타입드 배열 제네릭)
  const b = atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "="));
  const out = new Uint8Array(new ArrayBuffer(b.length));
  for (let i = 0; i < b.length; i++) out[i] = b.charCodeAt(i);
  return out;
}

async function key(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

/** readOnly(ro): 심사용 계정 – 관리 화면을 보고 미리보기는 하지만 승인·결정은 못 한다. */
export async function signSession(user: string, reviewer: boolean, secret: string, hours = SESSION_HOURS, readOnly = false): Promise<string> {
  const payload = b64url(enc.encode(JSON.stringify({ u: user, r: reviewer, ...(readOnly ? { ro: true } : {}), exp: Math.floor(Date.now() / 1000) + hours * 3600 })));
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", await key(secret), enc.encode(payload)));
  return `${payload}.${b64url(sig)}`;
}

/** 서명과 만료를 모두 확인한다. 하나라도 어긋나면 null — 호출부는 로그인 화면으로 보낸다. */
export async function readSession(token: string | undefined, secret: string): Promise<Session | null> {
  if (!token || !secret) return null;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return null;
  let ok = false;
  try {
    ok = await crypto.subtle.verify("HMAC", await key(secret), unb64url(sig), enc.encode(payload));
  } catch {
    return null;
  }
  if (!ok) return null;
  try {
    const { u, r, ro, exp } = JSON.parse(new TextDecoder().decode(unb64url(payload)));
    if (typeof u !== "string" || typeof exp !== "number" || exp < Date.now() / 1000) return null;
    return { user: u, reviewer: r === true, readOnly: ro === true, exp };
  } catch {
    return null;
  }
}
