"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { L, regionLabel } from "@/lib/labels";
import { READER_GENS, READER_REGIONS, TARGET_REGIONS, type Reader } from "@/lib/reader";

const control = "mt-2 block h-10 w-full max-w-[480px] rounded-md border border-hairline-strong bg-background px-3 text-[16px] text-ink sm:text-[14px] disabled:bg-surface-soft disabled:text-steel";
const help = "mt-1 max-w-[480px] text-[13px] leading-[1.5] text-steel";
const label = "block text-[14px] font-medium text-ink";
const outline = "inline-flex h-10 w-full items-center justify-center rounded-md border border-hairline-strong bg-background px-4 text-[14px] font-medium text-ink hover:border-ink sm:w-auto";

type Status = { kind: "saved" | "cleared" } | { kind: "error"; key: StringKey } | { kind: "signed_out" } | null;

/** 주소의 ?denied=review 를 한 번 보인 뒤 뺀다 — 저장하고 다시 그려도 권한 없음 알림이 남던 것. 화면은 다시 그리지 않는다. */
export function ForgetQuery({ path }: { path: string }) {
  useEffect(() => { window.history.replaceState(window.history.state, "", path); }, [path]);
  return null;
}

/** 내 설정. 설정은 계정에 저장한다 — 기기를 바꿔도 남고, 익명 방문자에게는 이 화면 자체가 없다.
 *  locked 면(예시 모드·저장값을 못 읽음) 칸을 잠근다 — 못 읽은 것을 빈 값으로 덮어쓰지 않게.
 *  account 는 맞춤 설정과 설정 지우기 사이에 놓는 계정 섹션(서버에서 그린다). */
export function ReaderForm({ initial, locale, locked = false, account }: { initial: Reader; locale: Locale; locked?: boolean; account?: React.ReactNode }) {
  const router = useRouter();
  const [r, setR] = useState<Reader>(initial);
  const [status, setStatus] = useState<Status>(null);
  const [adultError, setAdultError] = useState(false);
  const [busy, setBusy] = useState<"save" | "clear" | null>(null);
  const adultRef = useRef<HTMLInputElement>(null);
  const labels = L(locale);
  const others = READER_REGIONS.filter((c) => !TARGET_REGIONS.includes(c)).sort((a, b) => regionLabel(locale, a).localeCompare(regionLabel(locale, b), locale));

  const edit = (next: Reader) => { setR(next); if (status?.kind !== "signed_out") setStatus(null); };

  const save = async (next: Reader, kind: "save" | "clear") => {
    setBusy(kind);
    setStatus(null);
    try {
      const res = await fetch("/api/prefs", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(next) });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { code?: string };
        // 입력한 값은 그대로 둔다. 로그인이 끝났으면 다시 로그인할 길을 준다
        setStatus(body.code === "signed_out" ? { kind: "signed_out" } : { kind: "error", key: body.code === "sample" ? "pg_me_sample" : "me_save_failed" });
      } else {
        setR(next);
        setStatus({ kind: kind === "clear" ? "cleared" : "saved" });
        router.refresh();
      }
    } catch {
      setStatus({ kind: "error", key: "me_save_failed" });
    }
    setBusy(null);
  };

  const needAdult = r.gen === "10s";
  return (
    <div className="space-y-8">
      {status?.kind === "signed_out" && (
        <p role="alert" className="rounded-lg border border-hairline-strong px-4 py-3 text-[14px] leading-[1.55] text-ink">
          {t(locale, "pg_me_signed_out")}{" "}
          <Link href="/login?next=/me" className="text-link-blue hover:underline">{t(locale, "pg_me_sign_in_again")}</Link>
        </p>
      )}
      <section aria-labelledby="me-prefs" className="space-y-5">
        <div className="space-y-1.5">
          <h2 id="me-prefs" className="text-[18px] font-semibold text-ink">{t(locale, "pg_me_prefs")}</h2>
          <p className="text-[14px] leading-[1.55] text-charcoal">{t(locale, "pg_me_prefs_note")}</p>
          <p className="text-[13px] leading-[1.55] text-steel">{t(locale, "me_privacy")}</p>
        </div>
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (busy || locked) return;
            if (needAdult && !r.adult) {
              setAdultError(true);
              adultRef.current?.focus();
              return;
            }
            void save({ ...r, nick: r.nick?.trim() || undefined, adult: needAdult ? r.adult : undefined }, "save");
          }}
        >
          <fieldset disabled={locked} className="space-y-6">
            <div>
              <label htmlFor="reader-region" className={label}>{t(locale, "me_region")}</label>
              <select id="reader-region" value={r.region ?? ""} onChange={(e) => edit({ ...r, region: e.target.value || undefined })}
                aria-describedby="reader-region-help" className={control}>
                <option value="">{t(locale, "me_unset")}</option>
                <optgroup label={t(locale, "pg_me_target_regions")}>
                  {TARGET_REGIONS.map((c) => <option key={c} value={c}>{regionLabel(locale, c)}</option>)}
                </optgroup>
                <optgroup label={t(locale, "pg_me_other_regions")}>
                  {others.map((c) => <option key={c} value={c}>{regionLabel(locale, c)}</option>)}
                </optgroup>
              </select>
              <p id="reader-region-help" className={help}>{t(locale, "pg_me_region_help")}</p>
            </div>
            <div>
              <label htmlFor="reader-gen" className={label}>{t(locale, "me_gen")}</label>
              <select id="reader-gen" value={r.gen ?? ""} onChange={(e) => { setAdultError(false); edit({ ...r, gen: (e.target.value || undefined) as Reader["gen"], adult: false }); }}
                aria-describedby="reader-gen-help" className={control}>
                <option value="">{t(locale, "me_unset")}</option>
                {READER_GENS.map((g) => <option key={g} value={g}>{labels.generation[g]}</option>)}
              </select>
              <p id="reader-gen-help" className={help}>{t(locale, "pg_me_gen_help")}</p>
              {needAdult && (
                <div className="mt-3">
                  <label className="flex items-start gap-2 text-[14px] text-ink">
                    <input ref={adultRef} id="reader-adult" type="checkbox" checked={!!r.adult}
                      onChange={(e) => { setAdultError(false); edit({ ...r, adult: e.target.checked }); }}
                      aria-invalid={adultError || undefined} aria-describedby={adultError ? "reader-adult-error reader-adult-help" : "reader-adult-help"} className="mt-1 size-4" />
                    <span>{t(locale, "me_adult")}</span>
                  </label>
                  <p id="reader-adult-help" className={`${help} pl-6`}>{t(locale, "pg_me_adult_help")}</p>
                  {adultError && <p id="reader-adult-error" className="mt-1 pl-6 text-[13px] text-error">{t(locale, "pg_me_adult_error")}</p>}
                </div>
              )}
            </div>
            <div>
              <label htmlFor="reader-nick" className={label}>{t(locale, "me_nick")}</label>
              <input id="reader-nick" value={r.nick ?? ""} maxLength={20} onChange={(e) => edit({ ...r, nick: e.target.value })}
                aria-describedby="reader-nick-help" className={control} />
              <p id="reader-nick-help" className={help}>{t(locale, "pg_me_nick_help")}</p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button type="submit" aria-disabled={busy !== null || undefined} className="h-10 w-full rounded-md px-[18px] text-[14px] font-medium sm:w-auto">
                {busy === "save" ? t(locale, "pg_me_saving") : t(locale, "me_save")}
              </Button>
              <p role="status" aria-live="polite" className="text-[13px] text-charcoal">{status?.kind === "saved" ? t(locale, "me_saved") : ""}</p>
            </div>
            {status?.kind === "error" && <p role="alert" className="text-[13px] text-error">{t(locale, status.key)}</p>}
          </fieldset>
        </form>
      </section>

      {account}

      <section aria-labelledby="me-clear" className="space-y-3 border-t border-hairline pt-8">
        <h2 id="me-clear" className="text-[16px] font-semibold text-ink">{t(locale, "me_clear")}</h2>
        <p className="text-[14px] leading-[1.55] text-charcoal">{t(locale, "pg_me_clear_note")}</p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <button type="button" disabled={locked} aria-disabled={busy !== null || undefined}
            onClick={() => { if (!busy) void save({}, "clear"); }} className={`${outline} disabled:text-steel`}>
            {t(locale, "me_clear")}
          </button>
          <p role="status" aria-live="polite" className="text-[13px] text-charcoal">{status?.kind === "cleared" ? t(locale, "pg_me_cleared") : ""}</p>
        </div>
      </section>
    </div>
  );
}
