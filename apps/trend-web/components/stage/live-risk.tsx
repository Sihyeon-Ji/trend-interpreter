"use client";
/* 사전 항목의 '지금 다시 분류해 보기' – 검수자에게만 보인다(10-10 결정, ejchoi 계획 1단계).
   버튼을 누르면 최신 기사 제목을 GPU 의 Gemma 가 분류하고, 공개 판정과 같은 규칙으로 매긴 수준을 공개 판정 옆에 보인다.
   GPU 가 꺼져 있으면 기다리지 않고 '준비 안 됨' 을 보인다. 결과는 이 화면에만 – 공개 사전은 바뀌지 않는다. */
import { useState } from "react";
import type { Locale } from "@/lib/i18n";
import { Verdict, verdictOf } from "./bits";
import { tx } from "./copy";

type Sentence = { title: string; source: string; url: string; polarity: string; risk: string };
type LiveRisk = {
  status: "ok" | "not_ready" | "busy" | "too_few" | "source_unavailable" | "failed";
  level: string | null;
  reasons: string[];
  batch_level: string | null;
  same_as_batch: boolean | null;
  sentences: Sentence[];
  found: number;
  model: string | null;
  seconds: number | null;
  checked_at: string | null;
  cached: boolean;
};

const MESSAGE = { not_ready: "lr_not_ready", busy: "lr_busy", source_unavailable: "lr_source", failed: "lr_failed" } as const;

export function LiveRiskPanel({ termId, locale }: { termId: string; locale: Locale }) {
  const [state, setState] = useState<"idle" | "running" | "error">("idle");
  const [result, setResult] = useState<LiveRisk | null>(null);

  async function run() {
    setState("running");
    try {
      const res = await fetch(`/api/live-risk/${encodeURIComponent(termId)}`, { method: "POST" });
      if (!res.ok) throw new Error(String(res.status));
      setResult((await res.json()) as LiveRisk);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  const r = result;
  return (
    <section className="rs-block" aria-labelledby="rs-b-live">
      <h2 id="rs-b-live">{tx(locale, "lr_title")}</h2>
      <p className="rs-quiet">{tx(locale, "lr_note")}</p>
      <div className="rs-btns">
        <button type="button" className="rs-btn" onClick={run} disabled={state === "running"} aria-busy={state === "running"}>
          {tx(locale, state === "running" ? "lr_running" : "lr_run")}
        </button>
      </div>
      <div role="status" aria-live="polite">
        {state === "error" ? <p>{tx(locale, "lr_error")}</p> : null}
        {r && r.status !== "ok" ? (
          <p>{r.status === "too_few" ? tx(locale, "lr_too_few", { n: r.found }) : tx(locale, MESSAGE[r.status])}</p>
        ) : null}
        {r && r.status === "ok" ? (
          <div className="space-y-2">
            <dl className="rs-term-now">
              <div><dt>{tx(locale, "lr_now")}</dt><dd><Verdict kind={verdictOf({ risk_level: r.level, risk_checked_at: r.checked_at })} locale={locale} size="s" /></dd></div>
              <div><dt>{tx(locale, "lr_public")}</dt><dd><Verdict kind={verdictOf({ risk_level: r.batch_level, risk_checked_at: r.checked_at })} locale={locale} size="s" /></dd></div>
            </dl>
            <p>{tx(locale, r.same_as_batch ? "lr_same" : "lr_diff")}</p>
            {r.reasons.length ? <ul lang="ko">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul> : null}
            <ul className="rs-quiet">
              {r.sentences.map((x, i) => (
                <li key={i}>
                  <a href={x.url} target="_blank" rel="noreferrer">{x.title}</a> · {x.source} ·{" "}
                  {x.polarity === "offtopic" ? tx(locale, "lr_offtopic") : `${x.polarity}${x.risk !== "none" ? ` · ${x.risk}` : ""}`}
                </li>
              ))}
            </ul>
            <p className="rs-quiet">
              {tx(locale, "lr_meta", { n: r.found, s: r.seconds ?? "–", model: r.model ?? "–" })}
              {r.cached ? ` · ${tx(locale, "lr_cached")}` : ""}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
