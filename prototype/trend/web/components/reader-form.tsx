"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { t, type Locale } from "@/lib/i18n";
import { L, regionLabel } from "@/lib/labels";
import { READER_GENS, READER_REGIONS, type Reader } from "@/lib/reader";

export function ReaderForm({ initial, locale }: { initial: Reader; locale: Locale }) {
  const router = useRouter();
  const [r, setR] = useState<Reader>(initial);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 설정은 계정에 저장한다 — 기기를 바꿔도 남고, 익명 방문자에게는 이 화면 자체가 없다
  const save = async (next: Reader) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/prefs", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(next) });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setError(body.error ?? t(locale, "me_save_failed"));
        setBusy(false);
        return;
      }
      setR(next);
      setSaved(true);
      router.refresh();
    } catch {
      setError(t(locale, "me_save_failed"));
    }
    setBusy(false);
  };
  const needAdult = r.gen === "10s";
  const canSave = !needAdult || !!r.adult;
  const labels = L(locale);
  const field = "mt-1 block w-full rounded-[4px] border border-hairline bg-white px-3 py-2 text-[15px] text-ink";

  return (
    <form
      className="max-w-[520px] space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSave) return;
        void save({ ...r, nick: r.nick?.trim() || undefined, adult: needAdult ? r.adult : undefined });
      }}
    >
      <label className="block text-[13px] text-steel">
        {t(locale, "me_nick")}
        <input id="reader-nick" value={r.nick ?? ""} maxLength={20} onChange={(e) => setR({ ...r, nick: e.target.value })} placeholder={t(locale, "me_nick_ph")} className={field} />
      </label>
      <label className="block text-[13px] text-steel">
        {t(locale, "me_gen")}
        <select id="reader-gen" value={r.gen ?? ""} onChange={(e) => setR({ ...r, gen: (e.target.value || undefined) as Reader["gen"], adult: false })} className={field}>
          <option value="">{t(locale, "me_unset")}</option>
          {READER_GENS.map((g) => <option key={g} value={g}>{labels.generation[g]}</option>)}
        </select>
      </label>
      {needAdult && (
        <label className="flex items-start gap-2 text-[14px] text-charcoal">
          <input id="reader-adult" type="checkbox" checked={!!r.adult} onChange={(e) => setR({ ...r, adult: e.target.checked })} className="mt-1" />
          <span>{t(locale, "me_adult")}</span>
        </label>
      )}
      <label className="block text-[13px] text-steel">
        {t(locale, "me_region")}
        <select id="reader-region" value={r.region ?? ""} onChange={(e) => setR({ ...r, region: e.target.value || undefined })} className={field}>
          <option value="">{t(locale, "me_unset")}</option>
          {READER_REGIONS.map((c) => <option key={c} value={c}>{regionLabel(locale, c)}</option>)}
        </select>
      </label>
      <p className="text-[13px] leading-relaxed text-steel">{t(locale, "me_privacy")}</p>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!canSave || busy} className="h-10 rounded-lg px-[18px] text-[14px] font-medium">{t(locale, "me_save")}</Button>
        <button type="button" disabled={busy} onClick={() => void save({})} className="text-[13px] text-steel hover:text-ink disabled:text-faint">{t(locale, "me_clear")}</button>
        {saved && !error && <span className="text-[13px] text-charcoal">{t(locale, "me_saved")}</span>}
        {error && <span role="alert" className="text-[13px] text-error">{error}</span>}
      </div>
    </form>
  );
}
