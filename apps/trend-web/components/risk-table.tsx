"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { StatusBadge, type Tone } from "@/components/status-badge";
import { t, type Locale } from "@/lib/i18n";
import { fmtDate } from "@/lib/labels";
import { langTag, scriptLang } from "@/lib/lang";
import { reasonText } from "@/lib/reasons";
import { cn } from "@/lib/utils";

type Level = "none" | "caution" | "avoid";
/** rule: 규칙이 본 수준(검수자가 덮어도 따로 남는다). human: 검수자가 정한 수준. */
export interface RiskRow { term_id: string; canonical: string; lang?: string | null; rule: Level | null; human: Level | null; by: string | null; at: string | null; reasons: string[] }

const LEVEL_KEY = { none: "adm_level_none", caution: "adm_level_caution", avoid: "adm_level_avoid" } as const;
const TONE: Record<Level, Tone> = { none: "neutral", caution: "caution", avoid: "avoid" };
const levelName = (locale: Locale, l: Level | null) => t(locale, l ? LEVEL_KEY[l] : "adm_level_unknown");
const FIELD = "h-10 w-full rounded-md border border-hairline-strong bg-background px-2 text-[14px] text-ink sm:h-8 sm:text-[13px]";
const fill = (s: string, v: Record<string, string>) => Object.entries(v).reduce((acc, [k, x]) => acc.replace(`{${k}}`, x), s);

type Save = { state: "saving" | "saved" } | { state: "error"; message: string };

/** 리스크 수준을 사람이 바꾼다 — 행마다 선택 하나(검정 버튼 없음). 사람의 결정은 규칙보다 우선하고, '규칙대로' 를 고르면 지워진다.
 *  뜻 검수와 같이 같은 사이트의 /api/review 를 거친다 — 로그인 확인과 쓰기 토큰이 거기 있다. */
export function RiskTable({ rows, live = false, locale }: { rows: RiskRow[]; live?: boolean; locale: Locale }) {
  const router = useRouter();
  const [human, setHuman] = useState<Record<string, Level | null>>(Object.fromEntries(rows.map((r) => [r.term_id, r.human])));
  const [rule, setRule] = useState<Record<string, Level | null>>(Object.fromEntries(rows.map((r) => [r.term_id, r.rule])));
  const [save, setSave] = useState<Record<string, Save>>({});
  const [more, setMore] = useState<Record<string, boolean>>({});
  const [q, setQ] = useState("");
  const clear = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  useEffect(() => () => { for (const x of clear.current.values()) clearTimeout(x); }, []);

  const decide = async (termId: string, level: Level | null) => {
    const before = human[termId] ?? null;
    setHuman((h) => ({ ...h, [termId]: level }));
    const done = () => {
      setSave((s) => ({ ...s, [termId]: { state: "saved" } }));
      const old = clear.current.get(termId);
      if (old) clearTimeout(old);
      clear.current.set(termId, setTimeout(() => setSave((s) => { const n = { ...s }; delete n[termId]; return n; }), 3000));
    };
    if (!live) { done(); return; }
    setSave((s) => ({ ...s, [termId]: { state: "saving" } }));
    try {
      const res = await fetch(`/api/review/${encodeURIComponent(termId)}/risk`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ level }) });
      if (!res.ok) throw new Error(String(res.status));
      // 규칙이 방금 다시 본 수준 — '규칙대로' 를 고르면 이것이 보여야 한다(예전 사람의 값이 규칙인 척 남던 문제)
      const body = (await res.json()) as { risk_rule_level?: Level | null };
      setRule((prev) => ({ ...prev, [termId]: body.risk_rule_level ?? null }));
      done();
      router.refresh();                     // 탭 건수와 정한 사람·날짜를 다시 읽는다
    } catch (e) {
      const code = (e as Error).message;
      const key = code === "401" ? "adm_err_401" : code === "403" ? "adm_err_403" : "adm_err_other";
      setHuman((h) => ({ ...h, [termId]: before }));
      setSave((s) => ({ ...s, [termId]: { state: "error", message: t(locale, key) } }));
    }
  };

  const needle = q.trim().toLowerCase();
  const shown = rows.filter((r) => !needle || r.canonical.toLowerCase().includes(needle));
  const grid = "md:grid md:grid-cols-[160px_136px_minmax(0,1fr)_176px] md:gap-x-4 xl:grid-cols-[180px_140px_minmax(0,1fr)_120px_180px]";

  return (
    <div className="space-y-3">
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(locale, "adm_find")} aria-label={t(locale, "adm_find")}
        className="h-10 w-full rounded-md border border-hairline-strong bg-background px-3 text-[14px] text-ink placeholder:text-steel sm:h-8 sm:w-[240px] sm:text-[13px]" />
      {shown.length === 0 ? (
        <p className="rounded-lg border border-hairline px-6 py-6 text-[14px] text-charcoal">{fill(t(locale, "adm_no_match"), { q: q.trim() })}</p>
      ) : (
        <div>
          <div aria-hidden className={cn("hidden border-b border-hairline bg-surface px-3 py-2 text-[13px] font-medium text-steel", grid)}>
            <span>{t(locale, "adm_col_term")}</span>
            <span>{t(locale, "adm_risk_col_level")}</span>
            <span>{t(locale, "adm_risk_col_reasons")}</span>
            <span className="hidden xl:block">{t(locale, "adm_risk_col_by")}</span>
            <span>{t(locale, "adm_risk_col_change")}</span>
          </div>
          <ul className="divide-y divide-hairline border-b border-hairline">
            {shown.map((r) => {
              const h = human[r.term_id] ?? null;
              const ruled = rule[r.term_id] ?? null;
              const level = h ?? ruled;
              const lang = langTag(r.lang) ?? scriptLang(r.canonical);
              const reasons = r.reasons.filter((x) => x !== "검수자가 정한 수준");
              const open = more[r.term_id];
              const st = save[r.term_id];
              const who = h ? <><span className="text-charcoal">{r.by ?? ""}</span>{r.at && <span className="block tabular-nums text-steel">{fmtDate(r.at)}</span>}</> : <span className="text-steel">{t(locale, "adm_risk_rule")}</span>;
              return (
                <li key={r.term_id} className={cn("space-y-2 px-3 py-3 md:space-y-0", grid)}>
                  <div className="flex items-start justify-between gap-3 md:block">
                    <Link href={`/dictionary/${r.term_id}`} lang={lang} className="text-[15px] font-semibold text-ink hover:underline [overflow-wrap:break-word]">{r.canonical}</Link>
                    <span className="md:hidden"><StatusBadge tone={level ? TONE[level] : "muted"}>{levelName(locale, level)}</StatusBadge></span>
                  </div>
                  <div className="text-[13px] text-steel">
                    <span className="hidden md:inline"><StatusBadge tone={level ? TONE[level] : "muted"}>{levelName(locale, level)}</StatusBadge></span>
                    <span className="block md:mt-1">{t(locale, h ? "adm_risk_human" : "adm_risk_by_rule")}</span>
                    {h && h !== ruled && <span className="block">{fill(t(locale, "adm_risk_rule_says"), { level: levelName(locale, ruled) })}</span>}
                    <span className="block text-[13px] xl:hidden">{h && who}</span>
                  </div>
                  <div className="min-w-0 text-[13px] text-charcoal">
                    <span className="sr-only">{t(locale, "adm_risk_col_reasons")}</span>
                    {reasons.length ? (
                      <ul className="list-disc space-y-0.5 pl-4">
                        {(open ? reasons : reasons.slice(0, 2)).map((x) => { const y = reasonText(x, locale); return <li key={x} lang={scriptLang(y)} className={cn(!open && "line-clamp-2")}>{y}</li>; })}
                      </ul>
                    ) : <span className="text-steel">—</span>}
                    {reasons.length > 2 || reasons.some((x) => x.length > 90) ? (
                      <button type="button" onClick={() => setMore((m) => ({ ...m, [r.term_id]: !open }))} aria-expanded={!!open} className="mt-1 text-[13px] text-link-blue hover:underline">
                        {t(locale, open ? "adm_close_btn" : "adm_more_reasons")}
                      </button>
                    ) : null}
                  </div>
                  <div className="hidden text-[13px] xl:block">{who}</div>
                  <div className="space-y-1">
                    <select value={h ?? ""} onChange={(e) => void decide(r.term_id, (e.target.value || null) as Level | null)} disabled={st?.state === "saving"}
                      aria-label={fill(t(locale, "adm_change_aria"), { term: r.canonical })} className={FIELD}>
                      <option value="">{fill(t(locale, "adm_risk_follow"), { level: levelName(locale, ruled) })}</option>
                      {(["none", "caution", "avoid"] as Level[]).map((l) => <option key={l} value={l}>{levelName(locale, l)}</option>)}
                    </select>
                    <p aria-live="polite" className="min-h-[18px] text-[13px] text-steel">
                      {st?.state === "saving" ? t(locale, "adm_saving") : st?.state === "saved" ? `${t(locale, "adm_saved")}${live ? "" : ` ${t(locale, "adm_sample_note")}`}` : ""}
                    </p>
                    {st?.state === "error" && <p role="alert" className="text-[13px] text-avoid">{st.message}</p>}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

