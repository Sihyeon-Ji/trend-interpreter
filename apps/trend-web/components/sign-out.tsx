"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";

/** 로그아웃. variant="button" 은 내 설정의 외곽선 버튼, 기본은 관리 화면 머리의 글자 링크.
 *  요청이 실패하면 버튼을 다시 켜고 errorText 를 보인다(예전에는 꺼진 채 멈췄다). */
export function SignOut({ label, variant = "link", errorText }: { label: string; variant?: "link" | "button"; errorText?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-disabled={busy || undefined}
        onClick={async () => {
          if (busy) return;
          setBusy(true);
          setFailed(false);
          try {
            const res = await fetch("/api/auth/logout", { method: "POST" });
            if (!res.ok) throw new Error(String(res.status));
            router.replace("/");
            router.refresh();
          } catch {
            setBusy(false);
            setFailed(true);
          }
        }}
        className={cn(variant === "button"
          ? "inline-flex h-10 w-full items-center justify-center rounded-md border border-hairline-strong bg-background px-4 text-[14px] font-medium text-ink hover:border-ink sm:w-auto"
          : "text-[13px] text-steel underline-offset-2 hover:text-ink hover:underline", busy && "opacity-60")}
      >
        {label}
      </button>
      {failed && <span role="alert" className={cn("text-[13px] text-error", variant === "button" && "mt-2 block")}>{errorText ?? label}</span>}
    </>
  );
}
