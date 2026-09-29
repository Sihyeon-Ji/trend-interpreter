"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { afterLogin } from "@/lib/reader";

/* 라우트(app/api/auth/login)가 돌려주는 코드 → 화면 문구. 모르는 코드는 서버 문제로 본다. */
const SERVER_ERROR: Record<string, StringKey> = {
  not_configured: "pg_login_unavailable", unreachable: "pg_login_unavailable", failed: "pg_login_unavailable", bad_request: "pg_login_unavailable",
  sample: "pg_login_sample",
};

const field = "h-10 rounded-md border-hairline-strong bg-background px-3 text-[16px] shadow-none sm:text-[14px]";
const errorText = "text-[13px] leading-[1.5] text-error";

/** 로그인 폼. 버튼은 늘 켜 두고 누를 때 검사한다 — 미리 꺼 두면 왜 안 눌리는지 알 수 없다(2026-09-29 검토).
 *  스크립트가 붙기 전에 누른 Enter 도 비밀번호가 주소에 남지 않게 폼 자체를 POST 로 둔다(라우트가 303 으로 돌려보낸다). */
export function LoginForm({ locale, next, initialError = null }: { locale: Locale; next: string | null; initialError?: string | null }) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [missing, setMissing] = useState<{ user?: boolean; password?: boolean }>({});
  const [badCredentials, setBadCredentials] = useState(initialError === "bad_credentials");
  const [server, setServer] = useState<StringKey | null>(
    initialError && initialError !== "bad_credentials" && initialError !== "missing_fields" ? SERVER_ERROR[initialError] ?? "pg_login_unavailable" : null,
  );
  const [busy, setBusy] = useState(false);
  const userRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy) return;
    // 폼의 값을 읽는다 — 브라우저가 채운 저장된 비밀번호는 입력 이벤트 없이 들어와 상태에 없을 수 있다
    const form = new FormData(e.currentTarget);
    const u = String(form.get("username") ?? "").trim();
    const p = String(form.get("password") ?? "");
    setUser(u);
    setPassword(p);
    const miss = { user: !u, password: !p };
    setMissing(miss);
    setBadCredentials(false);
    setServer(null);
    if (miss.user) return userRef.current?.focus();
    if (miss.password) return passRef.current?.focus();

    setBusy(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ user: u, password: p }),
      });
      const body = (await res.json().catch(() => ({}))) as { code?: string; reviewer?: boolean };
      if (res.ok) {
        // 전체 이동. 클라이언트 라우팅으로 넘기면 세션이 안 잡혔을 때 버튼이 '로그인하는 중'에 멈춘 채로 남는다.
        window.location.assign(afterLogin(next, !!body.reviewer));
        return;
      }
      if (body.code === "bad_credentials") {
        setBadCredentials(true);
        passRef.current?.select();
      } else setServer(SERVER_ERROR[body.code ?? ""] ?? "pg_login_unavailable");
    } catch {
      setServer("pg_login_unavailable");
    }
    setBusy(false);
  };

  return (
    <form method="post" action="/api/auth/login" onSubmit={submit} className="space-y-5" noValidate>
      {next && <input type="hidden" name="next" value={next} />}
      <div className="space-y-2">
        <Label htmlFor="user" className="text-[14px] font-medium text-ink">{t(locale, "login_user")}</Label>
        <Input ref={userRef} id="user" name="username" autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false}
               value={user} onChange={(e) => { setUser(e.target.value); setMissing((m) => ({ ...m, user: false })); }} readOnly={busy}
               aria-invalid={missing.user || undefined} aria-describedby={missing.user ? "user-error" : undefined} className={field} />
        {missing.user && <p id="user-error" className={errorText}>{t(locale, "pg_login_need_user")}</p>}
      </div>
      <div className="space-y-2">
        <Label htmlFor="password" className="text-[14px] font-medium text-ink">{t(locale, "login_password")}</Label>
        <div className="relative">
          <Input ref={passRef} id="password" name="password" type={show ? "text" : "password"} autoComplete="current-password"
                 value={password} onChange={(e) => { setPassword(e.target.value); setMissing((m) => ({ ...m, password: false })); setBadCredentials(false); }} readOnly={busy}
                 aria-invalid={missing.password || badCredentials || undefined}
                 aria-describedby={missing.password ? "password-error" : badCredentials ? "password-bad" : undefined}
                 className={`${field} pr-16`} />
          <button type="button" onClick={() => setShow((v) => !v)} aria-pressed={show} aria-controls="password" aria-label={t(locale, "pg_login_show_password")}
            className="absolute inset-y-1 right-1 rounded px-2.5 text-[13px] text-charcoal hover:text-ink">
            {show ? t(locale, "pg_login_hide") : t(locale, "pg_login_show")}
          </button>
        </div>
        {missing.password && <p id="password-error" className={errorText}>{t(locale, "pg_login_need_password")}</p>}
        {badCredentials && <p id="password-bad" role="alert" className={errorText}>{t(locale, "login_failed")}</p>}
      </div>
      {server && <p role="alert" className="text-[14px] leading-[1.55] text-error">{t(locale, server)}</p>}
      <Button type="submit" aria-disabled={busy || undefined} className="h-10 w-full rounded-md text-[14px]">
        {busy ? t(locale, "login_working") : t(locale, "login_submit")}
      </Button>
    </form>
  );
}
