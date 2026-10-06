"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { t, type Locale } from "@/lib/i18n";

export function BatchDecision({ batchId, checksum, warnings, changed, locale }: {
  batchId: string; checksum: string; warnings: boolean; changed: boolean; locale: Locale;
}) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);
  const [exception, setException] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<"done" | "error" | null>(null);
  async function decide(decision: "approve" | "reject") {
    if (busy || message === "done") return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/publications/${encodeURIComponent(batchId)}`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ payload_sha256: checksum, decision, allow_gate_exceptions: exception }),
      });
      if (!response.ok) throw new Error("decision_failed");
      setMessage("done");
      router.refresh();
    } catch { setMessage("error"); }
    finally { setBusy(false); }
  }
  return <section className="space-y-4 border-t border-hairline pt-5">
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />{t(locale, "batch_check")}</label>
    {warnings && <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={exception} onChange={(event) => setException(event.target.checked)} />{t(locale, "batch_exception")}</label>}
    <div className="flex flex-wrap gap-3">
      <Button disabled={changed || !checked || (warnings && !exception) || busy || message === "done"} onClick={() => decide("approve")}>{t(locale, busy ? "batch_busy" : "batch_approve")}</Button>
      <Button variant="outline" disabled={!checked || busy || message === "done"} onClick={() => decide("reject")}>{t(locale, "batch_reject")}</Button>
    </div>
    {message && <p role="status" className="text-sm">{t(locale, message === "done" ? "batch_done" : "batch_error")}</p>}
  </section>;
}
