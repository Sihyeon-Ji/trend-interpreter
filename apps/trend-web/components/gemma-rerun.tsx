"use client";
/* 관리 화면 '수동 실행'(Gemma 실시간 분류 2단계, 10-10 결정: 첫 판은 미리보기).
   검수자가 용어를 5개까지 고르면 배치의 리스크 분류 단계를 한 용어씩 차례로 GPU 의 Gemma 로 다시 돌리고,
   저장된 분류·판정과 지금 분류·판정을 나란히 보인다. 아무것도 저장하지 않는다. GPU 가 꺼져 있으면 기다리지 않고 바로 알린다. */
import { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge, type Tone } from "@/components/status-badge";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";

type Level = "none" | "caution" | "avoid";
type Sentence = { text: string | null; source: string | null; kind: string; before_polarity: string | null; before_risk: string | null;
  polarity: string; risk: string; changed: boolean };
type Rerun = {
  status: "ok" | "not_ready" | "busy" | "too_few" | "failed";
  public_level: Level | null; before_level: Level | null; after_level: Level | null; after_reasons: string[];
  changed: number; sentences: Sentence[]; model: string | null; seconds: number | null; checked_at?: string | null;
  last?: Rerun | null;   // GPU 가 꺼져 있을 때 – 마지막 실제 실행 기록
};
type Recorded = { term_id: string; canonical: string; kind: "live" | "rerun"; run_at: string; level: Level | null; model: string | null };
type Gpu = { configured: boolean; ready: boolean; model: string | null; recorded?: Recorded[] };
type Row = { term_id: string; canonical: string; state: "idle" | "waiting" | "running" | "error"; result?: Rerun };

const MAX = 5;
const LEVEL_KEY = { none: "adm_level_none", caution: "adm_level_caution", avoid: "adm_level_avoid" } as const;
const TONE: Record<Level, Tone> = { none: "neutral", caution: "caution", avoid: "avoid" };
const MESSAGE = { not_ready: "adm_rerun_not_ready", busy: "adm_rerun_busy", too_few: "adm_rerun_too_few", failed: "adm_rerun_failed" } as const;
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replace(`{${k}}`, String(x)), s);

function LevelBadge({ level, locale }: { level: Level | null; locale: Locale }) {
  return <StatusBadge tone={level ? TONE[level] : "muted"}>{t(locale, level ? LEVEL_KEY[level] : "adm_level_unknown")}</StatusBadge>;
}

const label = (locale: Locale, polarity: string | null, risk: string | null) =>
  polarity === null ? t(locale, "adm_rerun_new") : `${polarity}${risk && risk !== "none" ? ` · ${risk}` : ""}`;

export function GemmaRerun({ terms, locale }: { terms: { term_id: string; canonical: string }[]; locale: Locale }) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [note, setNote] = useState<StringKey | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const running = rows.some((r) => r.state === "running" || r.state === "waiting");
  const [gpu, setGpu] = useState<Gpu | "checking" | "error">("checking");

  const [round, setRound] = useState(0);              // '다시 확인' 을 누를 때마다 하나씩
  useEffect(() => {                                     // 데모 전 예열 확인 – 모델은 부르지 않는다
    let live = true;
    fetch("/api/gpu-status", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((g: Gpu) => { if (live) setGpu(g); }, () => { if (live) setGpu("error"); });
    return () => { live = false; };
  }, [round]);
  const check = () => { setGpu("checking"); setRound((n) => n + 1); };

  function add() {
    const q = query.trim();
    const hit = terms.find((x) => x.canonical === q || x.term_id === q);
    if (!hit) return setNote("adm_rerun_unknown");
    if (rows.length >= MAX) return setNote("adm_rerun_max");
    if (!rows.some((r) => r.term_id === hit.term_id)) setRows((rs) => [...rs, { ...hit, state: "idle" }]);
    setQuery("");
    setNote(null);
  }

  const patch = (termId: string, p: Partial<Row>) => setRows((rs) => rs.map((r) => (r.term_id === termId ? { ...r, ...p } : r)));

  async function run() {
    const ids = rows.map((r) => r.term_id);
    setRows((rs) => rs.map((r) => ({ term_id: r.term_id, canonical: r.canonical, state: "waiting" })));
    for (const termId of ids) {                       // GPU 한 장 – 한 용어씩 차례로
      patch(termId, { state: "running" });
      try {
        const res = await fetch(`/api/risk-rerun/${encodeURIComponent(termId)}`, { method: "POST" });
        if (!res.ok) throw new Error(String(res.status));
        patch(termId, { state: "idle", result: (await res.json()) as Rerun });
      } catch {
        patch(termId, { state: "error" });
      }
    }
  }

  return (
    <section aria-labelledby="st-rerun" className="space-y-3 pt-4">
      <h2 id="st-rerun" className="text-[16px] font-semibold text-ink">{t(locale, "adm_rerun_title")}</h2>
      <p className="text-[13px] text-steel">{t(locale, "adm_rerun_note")}</p>
      <p className="text-[13px] text-charcoal">{t(locale, "adm_rerun_stage")}</p>
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <span className="text-steel">{t(locale, "adm_gpu_label")}</span>
        <span role="status" aria-live="polite" data-gpu={typeof gpu === "string" ? gpu : gpu.ready ? "ready" : gpu.configured ? "off" : "none"}>
          {gpu === "checking" ? <span className="text-steel">{t(locale, "adm_gpu_checking")}</span>
            : gpu === "error" ? <StatusBadge tone="muted">{t(locale, "adm_gpu_error")}</StatusBadge>
            : gpu.ready ? <StatusBadge tone="good">{fill(t(locale, "adm_gpu_ready"), { model: gpu.model ?? "–" })}</StatusBadge>
            : <StatusBadge tone="muted">{t(locale, gpu.configured ? "adm_gpu_off" : "adm_gpu_none")}</StatusBadge>}
        </span>
        <button type="button" className="text-steel underline underline-offset-2 hover:text-ink disabled:opacity-40" onClick={check} disabled={gpu === "checking"}>
          {t(locale, "adm_gpu_recheck")}
        </button>
      </div>
      {typeof gpu !== "string" && (
        <div className="space-y-1.5 rounded-md bg-surface px-3 py-2.5">
          <p className="text-[13px] font-semibold text-ink">{t(locale, "adm_recorded_title")}</p>
          <p className="text-[12px] text-steel">{t(locale, "adm_recorded_note")}</p>
          {gpu.recorded && gpu.recorded.length > 0 ? (
            <ul className="space-y-1 text-[13px]" aria-label={t(locale, "adm_recorded_title")}>
              {gpu.recorded.map((x) => (
                <li key={`${x.term_id}-${x.kind}`} className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <a href={`/dictionary/${encodeURIComponent(x.term_id)}`} className="font-medium text-ink underline underline-offset-2">{x.canonical}</a>
                  <span className="text-steel">{t(locale, x.kind === "live" ? "adm_recorded_live" : "adm_recorded_rerun")}</span>
                  <LevelBadge level={x.level} locale={locale} />
                  <span className="tabular-nums text-steel">{fmtDateTime(x.run_at, locale)} · {x.model ?? "–"}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-[13px] text-charcoal">{t(locale, "adm_recorded_none")}</p>}
        </div>
      )}
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); add(); }}>
        <label className="space-y-1 text-[13px] text-steel" htmlFor={`${id}-q`}>
          <span className="block">{t(locale, "adm_rerun_pick")}</span>
          <Input id={`${id}-q`} list={`${id}-terms`} value={query} onChange={(e) => setQuery(e.target.value)} disabled={running}
            className="h-9 w-64 max-w-full" autoComplete="off" />
        </label>
        <datalist id={`${id}-terms`}>{terms.map((x) => <option key={x.term_id} value={x.canonical} />)}</datalist>
        <Button type="submit" variant="outline" className="h-9 rounded-md border-hairline-strong px-3 shadow-none" disabled={running || !query.trim()}>
          {t(locale, "adm_rerun_add")}
        </Button>
      </form>
      {note ? <p role="alert" className="text-[13px] text-caution">{t(locale, note)}</p> : null}
      {rows.length > 0 && (
        <>
          <ul className="flex flex-wrap gap-2" aria-label={t(locale, "adm_rerun_pick")}>
            {rows.map((r) => (
              <li key={r.term_id} className="flex items-center gap-1 rounded-md border border-hairline px-2 py-1 text-[13px] text-ink">
                {r.canonical}
                <button type="button" className="px-1 text-steel hover:text-ink disabled:opacity-40" disabled={running}
                  aria-label={fill(t(locale, "adm_rerun_remove"), { term: r.canonical })}
                  onClick={() => setRows((rs) => rs.filter((x) => x.term_id !== r.term_id))}>×</button>
              </li>
            ))}
          </ul>
          <Button type="button" className="h-9 rounded-md px-4" onClick={run} disabled={running} aria-busy={running}>
            {t(locale, running ? "adm_rerun_running" : "adm_rerun_run")}
          </Button>
          <div className="space-y-4" role="log" aria-live="polite" aria-label={t(locale, "adm_rerun_title")}>
            {rows.filter((r) => r.state !== "idle" || r.result).map((r) => (
              <RerunResult key={r.term_id} row={r} locale={locale} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function RerunResult({ row, locale }: { row: Row; locale: Locale }) {
  const r = row.result;
  return (
    <article className="space-y-2 border-t border-hairline pt-3" aria-label={row.canonical}>
      <h3 className="text-[15px] font-semibold text-ink">{row.canonical}</h3>
      {row.state === "waiting" && <p className="text-[13px] text-steel">{t(locale, "adm_rerun_waiting")}</p>}
      {row.state === "running" && <p className="text-[13px] text-steel">{t(locale, "adm_rerun_running")}</p>}
      {row.state === "error" && <p className="text-[13px] text-avoid">{t(locale, "adm_rerun_error")}</p>}
      {row.state === "idle" && r && r.status !== "ok" && <p className="text-[13px] text-charcoal">{t(locale, MESSAGE[r.status])}</p>}
      {row.state === "idle" && r && r.status !== "ok" && r.last && (
        <>
          <p className="text-[13px] font-medium text-ink">{fill(t(locale, "adm_rerun_last"), { date: r.last.checked_at ? fmtDateTime(r.last.checked_at, locale) : "–" })}</p>
          <RerunBody r={r.last} locale={locale} />
        </>
      )}
      {row.state === "idle" && r && r.status === "ok" && <RerunBody r={r} locale={locale} />}
    </article>
  );
}

function RerunBody({ r, locale }: { r: Rerun; locale: Locale }) {
  return (
        <>
          <dl className="flex flex-wrap gap-x-6 gap-y-2 text-[13px]">
            <div className="space-y-1"><dt className="text-steel">{t(locale, "adm_rerun_before")}</dt><dd><LevelBadge level={r.before_level} locale={locale} /></dd></div>
            <div className="space-y-1"><dt className="text-steel">{t(locale, "adm_rerun_after")}</dt><dd><LevelBadge level={r.after_level} locale={locale} /></dd></div>
            <div className="space-y-1"><dt className="text-steel">{t(locale, "adm_rerun_public")}</dt><dd><LevelBadge level={r.public_level} locale={locale} /></dd></div>
          </dl>
          {r.after_reasons.length > 0 && <ul lang="ko" className="list-disc pl-5 text-[13px] text-charcoal">{r.after_reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>}
          <p className="text-[13px] text-charcoal">{fill(t(locale, "adm_rerun_changed"), { n: r.changed, total: r.sentences.length })}</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] table-fixed text-left text-[13px]">
              <colgroup><col /><col className="w-[140px]" /><col className="w-[140px]" /></colgroup>
              <thead className="border-b border-hairline bg-surface text-steel">
                <tr>
                  <th scope="col" className="px-2 py-1.5 font-medium">{t(locale, "adm_rerun_th_text")}</th>
                  <th scope="col" className="px-2 py-1.5 font-medium">{t(locale, "adm_rerun_th_before")}</th>
                  <th scope="col" className="px-2 py-1.5 font-medium">{t(locale, "adm_rerun_th_after")}</th>
                </tr>
              </thead>
              <tbody>
                {r.sentences.map((s, i) => (
                  <tr key={i} className="border-b border-hairline align-top" data-changed={s.changed || undefined}>
                    <td className="px-2 py-1.5 text-ink [overflow-wrap:anywhere]">
                      {s.text ? <>{s.text} <span className="text-steel">· {s.source}</span></> : <span className="text-steel">{t(locale, "adm_rerun_post")}</span>}
                    </td>
                    <td className="px-2 py-1.5 text-charcoal">{label(locale, s.before_polarity, s.before_risk)}</td>
                    <td className={s.changed ? "px-2 py-1.5 font-semibold text-ink" : "px-2 py-1.5 text-charcoal"}>{label(locale, s.polarity, s.risk)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[13px] text-steel">{fill(t(locale, "adm_rerun_meta"), { s: r.seconds ?? "–", model: r.model ?? "–" })}</p>
        </>
  );
}
