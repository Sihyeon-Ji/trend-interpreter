"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ExplainCards, ResultHeader, foundSummary } from "@/components/explain-cards";
import { ChatCards, type ChatCard } from "@/components/chat-cards";
import type { ExplainResult } from "@/lib/explain";
import { t, type Locale } from "@/lib/i18n";

const MAX = 500;   // app/api/chat 와 백엔드가 이 길이에서 자른다 — 알리지 않고 자르지 않게 칸에서 막는다

type Entry =
  | { kind: "explain"; input: string; result: ExplainResult }
  | { kind: "answer"; input: string; text: string; termIds: string[]; cards: ChatCard[] }
  | { kind: "none"; input: string }         // 백엔드가 답했는데 사전에 없는 말
  | { kind: "sample"; input: string };      // 예시 데이터라 질문에 답할 수 없다

type StreamResult = { answer: string; term_ids?: string[]; cards?: unknown[] };

/** SSE 를 읽어 진행 상황은 화면에 흘리고, 마지막 result 를 돌려준다. event: error 는 실패로 알린다(예전에는 버려서 '사전에 없다' 로 보였다). */
async function readStream(body: ReadableStream<Uint8Array>, onProgress: (s: string) => void): Promise<StreamResult | "error" | null> {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let out: StreamResult | "error" | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    buf = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const ev = /^event:\s*(.+)$/m.exec(chunk)?.[1]?.trim();
      const raw = /^data:\s*(.+)$/m.exec(chunk)?.[1];
      if (ev === "error") { out = "error"; continue; }
      if (!ev || !raw) continue;
      try {
        const data = JSON.parse(raw);
        if (ev === "progress") onProgress(String(data.label ?? ""));
        else if (ev === "result") out = data as StreamResult;
      } catch {
        // 조각난 줄은 버린다
      }
    }
  }
  return out;
}

/** 카드에 실려 온 표제어 이름 찾기. 참고한 항목을 이름으로 적기 위해서다. */
function nameOf(cards: ChatCard[], id: string): string | null {
  for (const c of cards) {
    if (c.type === "term" && c.term_id === id) return c.canonical;
    if (c.type === "list") {
      const hit = c.items.find((i) => i.term_id === id);
      if (hit) return hit.canonical;
    }
    if (c.type === "usage" && c.term_id === id) return c.term;
  }
  return null;
}

const summaryOf = (locale: Locale, e: Entry) =>
  e.kind === "explain" ? foundSummary(locale, e.result.items.length)
    : e.kind === "answer" ? t(locale, "pg_ex_answer")
      : e.kind === "none" ? t(locale, "pg_ex_not_in_dict") : t(locale, "pg_ex_sample_only_short");

/** 결과 본문(머리 제외). 지금 결과와 '이전 결과' 가 같은 모양을 쓴다. */
function EntryBody({ entry, locale }: { entry: Entry; locale: Locale }) {
  if (entry.kind === "explain") return <ExplainCards result={entry.result} locale={locale} original={entry.input} />;
  const question = (
    <dl className="grid gap-x-4 gap-y-1 border-b border-hairline pb-3 sm:grid-cols-[112px_minmax(0,1fr)]">
      <dt className="text-[13px] font-medium text-steel">{t(locale, "pg_ex_question")}</dt>
      <dd className="text-[15px] leading-[1.6] whitespace-pre-wrap text-ink">{entry.input}</dd>
    </dl>
  );
  if (entry.kind === "none") {
    return (
      <div className="space-y-3">
        {question}
        <p className="text-[15px] leading-[1.6] text-charcoal">{t(locale, "chat_none")}</p>
        <Link href={`/dictionary?q=${encodeURIComponent(entry.input.slice(0, 40))}`} className="inline-block text-[14px] text-link-blue hover:underline">{t(locale, "pg_ex_search_dict")}</Link>
      </div>
    );
  }
  if (entry.kind === "sample") {
    return (
      <div className="space-y-3">
        {question}
        <p className="text-[15px] leading-[1.6] text-charcoal">{t(locale, "pg_ex_sample_only")}</p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {question}
      {/* 답 글은 카드가 담지 못하는 것(왜·비교)만 말한다 — 카드와 같은 내용을 되풀이하지 않는다(2026-09-16 검토) */}
      <p className="max-w-[720px] text-[15px] leading-[1.6] whitespace-pre-wrap text-ink">{entry.text}</p>
      <ChatCards cards={entry.cards} locale={locale} />
      {entry.termIds.length > 0 && (
        <p className="text-[13px] leading-[1.6] text-steel">
          {t(locale, "chat_from")}{" "}
          {entry.termIds.slice(0, 8).map((id, k) => (
            <span key={id}>
              {k > 0 && ", "}
              <Link href={`/dictionary/${id}`} className="text-link-blue hover:underline">{nameOf(entry.cards, id) ?? t(locale, "chat_entry")}</Link>
            </span>
          ))}
          {entry.termIds.length > 8 && ` ${t(locale, "pg_ex_more").replace("{n}", String(entry.termIds.length - 8))}`}
        </p>
      )}
    </div>
  );
}

/** 메시지 해석 화면의 입력과 결과. 입력이 맨 위이고, 서버가 미리 풀어 둔 예시(example)는 사용자가 처음 해석하면 결과로 바뀐다.
 *  결과는 셋으로 나눈다: 찾음·답(결과), 없음(사전에 없는 말), 실패(입력 칸 아래 알림 — 입력은 그대로 둔다). */
export function DictionaryChat({ locale, sample = false, sampleText, example }: { locale: Locale; sample?: boolean; sampleText: string; example?: React.ReactNode }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [failed, setFailed] = useState(false);
  const [empty, setEmpty] = useState(false);
  const [clipped, setClipped] = useState(false);
  const [live, setLive] = useState("");                 // 화면 읽기 프로그램에 알리는 짧은 문장 하나
  const heading = useRef<HTMLHeadingElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!entries.length) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    heading.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    heading.current?.focus({ preventScroll: true });
  }, [entries.length]);

  async function run(raw: string) {
    const text = raw.trim();
    if (busy) return;
    if (!text) {
      setEmpty(true);
      input.current?.focus();
      return;
    }
    setEmpty(false);
    setFailed(false);
    setBusy(true);
    setLive(t(locale, "pg_ex_working"));
    const push = (e: Entry, say: string) => {
      setEntries((prev) => [...prev, e]);
      setDraft("");                      // 입력은 성공했을 때만 비운다
      setClipped(false);
      setLive(say);
    };
    const nothing = () => (sample ? push({ kind: "sample", input: text }, t(locale, "pg_ex_sample_only_short")) : push({ kind: "none", input: text }, t(locale, "pg_ex_not_in_dict")));
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        // 바로 앞 대화를 함께 보낸다 — "비슷한 것도 없어?" 같은 말을 알아듣게. 카드 내용은 보내지 않는다.
        body: JSON.stringify({
          text,
          locale,
          history: entries.slice(-3).flatMap((x) => [{ role: "user", content: x.input }, ...(x.kind === "answer" ? [{ role: "assistant", content: x.text }] : [])]),
        }),
      });
      if (!res.ok) throw new Error(String(res.status));
      if (res.headers.get("content-type")?.includes("event-stream") && res.body) {
        const done = await readStream(res.body, setProgress);
        if (done === "error" || done === null) {
          // 스트림이 결과 없이 끝나면 실패다. 예시 데이터에서는 질문 답변이 없다고 알린다
          if (sample) nothing();
          else throw new Error("stream");
        } else if (done.answer) {
          const cards = (done.cards ?? []) as ChatCard[];
          push({ kind: "answer", input: text, text: done.answer, termIds: done.term_ids ?? [], cards }, t(locale, "pg_ex_answer"));
        } else nothing();
      } else {
        const body = await res.json();
        if (body.kind === "explain") {
          const result = body.result as ExplainResult;
          push({ kind: "explain", input: text, result }, foundSummary(locale, result.items.length));
        } else if (body.failed) {
          if (sample) nothing();           // 예시 모드는 질문 경로의 백엔드가 없다 — '사전에 없다' 고 말하지 않는다
          else throw new Error("failed");
        } else if (body.answer) {
          push({ kind: "answer", input: text, text: body.answer as string, termIds: (body.termIds ?? []) as string[], cards: (body.cards ?? []) as ChatCard[] }, t(locale, "pg_ex_answer"));
        } else nothing();
      }
    } catch {
      setFailed(true);
      setLive(t(locale, "chat_failed"));
    }
    setProgress("");
    setBusy(false);
  }

  const current = entries.at(-1);
  const previous = entries.slice(0, -1).reverse();
  const examples = [
    { label: t(locale, "pg_ex_try_comment"), text: sampleText },
    // 예시 데이터에는 질문 답변이 없다 — 누르면 안 되는 예시는 보이지 않는다
    ...(sample ? [] : [{ label: t(locale, "pg_ex_try_q1"), text: t(locale, "pg_ex_try_q1") }, { label: t(locale, "pg_ex_try_q2"), text: t(locale, "pg_ex_try_q2") }]),
  ];
  const describedBy = ["chat-help", "chat-count", empty && "chat-empty", sample && "chat-sample"].filter(Boolean).join(" ");

  return (
    <div className="space-y-8">
      <p role="status" className="sr-only">{live}</p>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void run(draft); }}>
        <label htmlFor="chat-input" className="block text-[14px] font-medium text-ink">{t(locale, "pg_ex_input_label")}</label>
        <Textarea
          ref={input}
          id="chat-input"
          value={draft}
          maxLength={MAX}
          readOnly={busy}
          onChange={(e) => { setDraft(e.target.value); setEmpty(false); }}
          onPaste={(e) => { if (draft.length + e.clipboardData.getData("text").length > MAX) setClipped(true); }}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void run(draft); } }}
          placeholder={t(locale, "chat_placeholder")}
          aria-invalid={empty || undefined}
          aria-describedby={describedBy}
          className="min-h-[104px] resize-y rounded-md border-hairline-strong bg-white p-3 text-[16px] leading-[1.6] text-ink shadow-none"
          spellCheck={false}
        />
        <div className="flex items-start justify-between gap-4 text-[13px] leading-[1.5] text-steel">
          <p id="chat-help">
            {t(locale, "chat_helper")}
            <span className="hidden sm:inline"> {t(locale, "pg_ex_shortcut")}</span>
          </p>
          <p id="chat-count" className="shrink-0 tabular-nums">
            {clipped ? <span className="text-charcoal">{t(locale, "pg_ex_clipped")}</span> : `${draft.length}/${MAX}`}
          </p>
        </div>
        {sample && <p id="chat-sample" className="text-[13px] leading-[1.5] text-steel">{t(locale, "pg_ex_sample_only")}</p>}
        {empty && <p id="chat-empty" className="text-[13px] text-error">{t(locale, "pg_ex_empty")}</p>}
        {failed && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-[14px] text-error">
            <span>{t(locale, "chat_failed")}</span>
            <Button type="button" variant="outline" onClick={() => void run(draft)} className="h-9 rounded-md border-hairline-strong px-3 text-[13px] text-ink">{t(locale, "pg_ex_retry")}</Button>
          </div>
        )}
        <Button type="submit" aria-disabled={busy || undefined} className="h-11 w-full rounded-md px-[18px] text-[14px] font-medium sm:h-10 sm:w-auto">
          {busy ? t(locale, "pg_ex_working") : t(locale, "chat_send")}
        </Button>
        {busy && <p className="text-[14px] text-steel">{(locale === "ko" && progress) || t(locale, "chat_thinking")}</p>}
        <div className="space-y-2 pt-1">
          <p className="text-[13px] text-steel">{t(locale, "pg_ex_try")}</p>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
            {examples.map((x) => (
              <button key={x.label} type="button" onClick={() => { setDraft(x.text); void run(x.text); }}
                className="inline-flex h-10 shrink-0 items-center rounded-md border border-hairline-strong bg-background px-3 text-[13px] whitespace-nowrap text-charcoal hover:border-ink hover:text-ink sm:h-8">
                {x.label}
              </button>
            ))}
          </div>
        </div>
      </form>

      {current ? (
        <section aria-labelledby="result-heading" className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <ResultHeader locale={locale} headingRef={heading} headingId="result-heading" summary={summaryOf(locale, current)} />
            <Button type="button" variant="outline" onClick={() => { setEntries([]); setLive(""); }} className="h-9 shrink-0 rounded-md border-hairline-strong px-3 text-[13px] text-ink">
              {t(locale, "pg_ex_reset")}
            </Button>
          </div>
          <EntryBody entry={current} locale={locale} />
        </section>
      ) : example}

      {previous.length > 0 && (
        <section aria-labelledby="history-heading" className="space-y-2 border-t border-hairline pt-6">
          <h2 id="history-heading" className="text-[16px] font-semibold text-ink">{t(locale, "pg_ex_history")}</h2>
          <ul className="divide-y divide-hairline">
            {previous.map((e, i) => (
              <li key={entries.length - 2 - i}>
                <details className="group py-3">
                  <summary className="flex cursor-pointer items-baseline justify-between gap-4 text-[14px]">
                    <span className="min-w-0 truncate text-ink">{e.input.split("\n")[0]}</span>
                    <span className="shrink-0 text-[13px] text-steel">{summaryOf(locale, e)}</span>
                  </summary>
                  <div className="pt-4"><EntryBody entry={e} locale={locale} /></div>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
