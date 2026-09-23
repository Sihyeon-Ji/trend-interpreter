"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function SignOut({ label }: { label: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await fetch("/api/auth/logout", { method: "POST" });
        router.replace("/");
        router.refresh();
      }}
      className="text-[13px] text-steel underline-offset-2 hover:text-ink hover:underline disabled:text-faint"
    >
      {label}
    </button>
  );
}
