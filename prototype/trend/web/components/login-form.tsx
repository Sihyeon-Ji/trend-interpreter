"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t, type Locale } from "@/lib/i18n";

export function LoginForm({ locale, next }: { locale: Locale; next: string }) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ user, password }),
      });
      if (res.ok) {
        // 전체 이동. 클라이언트 라우팅으로 넘기면 세션이 안 잡혔을 때 버튼이 '확인하는 중'에 멈춘 채로 남는다.
        window.location.assign(next);
        return;
      }
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      setError(body.error ?? t(locale, "login_failed"));
    } catch {
      setError(t(locale, "login_failed"));
    }
    setBusy(false);
  };

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="user" className="text-[13px] text-charcoal">{t(locale, "login_user")}</Label>
        <Input id="user" name="username" autoComplete="username" autoCapitalize="none" autoCorrect="off" required
               value={user} onChange={(e) => setUser(e.target.value)}
               className="h-10 rounded-md border-hairline-strong bg-background shadow-none" />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="password" className="text-[13px] text-charcoal">{t(locale, "login_password")}</Label>
        <Input id="password" name="password" type="password" autoComplete="current-password" required
               value={password} onChange={(e) => setPassword(e.target.value)}
               className="h-10 rounded-md border-hairline-strong bg-background shadow-none" />
      </div>
      {error && <p role="alert" className="text-[13px] text-error">{error}</p>}
      <Button type="submit" disabled={busy || !user.trim() || !password} className="h-10 w-full rounded-md">
        {busy ? t(locale, "login_working") : t(locale, "login_submit")}
      </Button>
    </form>
  );
}
