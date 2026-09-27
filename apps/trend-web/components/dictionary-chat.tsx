"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ExplainCards } from "@/components/explain-cards";
import { ChatCards, type ChatCard } from "@/components/chat-cards";
import type { ExplainResult } from "@/lib/explain";
import { t, type Locale } from "@/lib/i18n";

type Turn =
  | { role: "user"; text: string }
  | { role: "explain"; result: ExplainResult }
  | { role: "answer"; text: string; termIds: string[]; cards: ChatCard[] }
  | { role: "empty" };

type StreamResult = { answer: string; term_ids?: string[]; cards?: unknown[] };

/** SSE 를 읽어 진행 상황은 화면에 흘리고, 마지막 result 만 돌려준다. */
async function readStream(body: ReadableStream<Uint8Array>, onProgress: (s: string) => void): Promise<StreamResult | null> {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let out: StreamResult | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    buf = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const ev = /^event:\s*(.+)$/m.exec(chunk)?.[1]?.trim();
      const raw = /^data:\s*(.+)$/m.exec(chunk)?.[1];
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

/** 카드에 실려 온 표제어 이름 찾기. 근거 줄을 이름으로 적기 위해서다. */
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

export function DictionaryChat({ locale, initial }: { locale: Locale; initial?: { text: string; result: ExplainResult } }) {
  const [turns, setTurns] = useState<Turn[]>(
    initial ? [{ role: "user", text: initial.text }, { role: "explain", result: initial.result }] : [],
  );
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<string>("");   // 지금 무엇을 하는 중인지
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (turns.length > 2) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns.length]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setError(null);
    setBusy(true);
    setTurns((prev) => [...prev, { role: "user", text }]);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        // 바로 앞 대화를 함께 보낸다 — "비슷한 것도 없어?" 같은 말을 알아듣게. 카드 내용은 보내지 않는다.
        body: JSON.stringify({
          text,
          locale,
          history: turns
            .slice(-6)
            .map((x) => (x.role === "user" ? { role: "user", content: x.text } : x.role === "answer" ? { role: "assistant", content: x.text } : null))
            .filter((x): x is { role: string; content: string } => !!x),
        }),
      });
      // 서버가 진행 상황을 흘려보내면(text/event-stream) 받아 가며 보여 준다.
      if (res.ok && res.headers.get("content-type")?.includes("event-stream") && res.body) {
        const done = await readStream(res.body, setProgress);
        if (done?.answer) {
          setTurns((prev) => [...prev, { role: "answer", text: done.answer, termIds: done.term_ids ?? [], cards: (done.cards ?? []) as ChatCard[] }]);
        } else {
          setTurns((prev) => [...prev, { role: "empty" }]);
        }
      } else {
        const body = await res.json();
        if (!res.ok) {
          setError(body?.error ?? t(locale, "chat_failed"));
        } else if (body.kind === "explain") {
          setTurns((prev) => [...prev, { role: "explain", result: body.result as ExplainResult }]);
        } else if (body.answer) {
          setTurns((prev) => [...prev, { role: "answer", text: body.answer as string, termIds: (body.termIds ?? []) as string[], cards: (body.cards ?? []) as ChatCard[] }]);
        } else {
          setTurns((prev) => [...prev, { role: "empty" }]);
        }
      }
    } catch {
      setError(t(locale, "chat_failed"));
    }
    setProgress("");
    setBusy(false);
  }

  return (
    <div className="space-y-6">
      <div className="space-y-6" aria-live="polite" aria-busy={busy}>
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <p key={i} className="ml-auto max-w-[80%] rounded-lg bg-surface px-3 py-2 text-[15px] leading-[1.6] whitespace-pre-wrap text-ink">{turn.text}</p>
          ) : turn.role === "explain" ? (
            <ExplainCards key={i} result={turn.result} locale={locale} />
          ) : turn.role === "answer" ? (
            <div key={i} className="space-y-2">
              {/* 카드가 먼저다. 본문은 카드가 담지 못하는 것(왜·비교)만 말한다 —
                  카드와 같은 내용을 글로 되풀이하면 같은 걸 두 번 읽힌다(2026-09-16 검토). */}
              <ChatCards cards={turn.cards} locale={locale} />
              <p className="max-w-[80%] text-[16px] leading-[1.7] whitespace-pre-wrap text-ink">{turn.text}</p>
              {turn.termIds.length > 0 && (
                <p className="text-[13px] text-steel">
                  {t(locale, "chat_from")}{" "}
                  {/* 표제어 이름으로 적는다. "사전 항목"을 열두 번 반복하면 근거가 아니라 잡음이다. */}
                  {turn.termIds.slice(0, 8).map((id, k) => (
                    <span key={id}>
                      {k > 0 && ", "}
                      <Link href={`/dictionary/${id}`} className="text-link-blue hover:underline">
                        {nameOf(turn.cards, id) ?? t(locale, "chat_entry")}
                      </Link>
                    </span>
                  ))}
                  {turn.termIds.length > 8 && ` 외 ${turn.termIds.length - 8}`}
                </p>
              )}
            </div>
          ) : (
            <p key={i} className="max-w-[80%] text-[15px] text-charcoal">{t(locale, "chat_none")}</p>
          ),
        )}
        {busy && (
          <p className="text-[14px] text-steel" aria-live="polite">
            {progress || t(locale, "chat_thinking")}
          </p>
        )}
        {error && <p role="alert" className="text-[14px] text-error">{error}</p>}
        <div ref={end} />
      </div>

      <form className="space-y-2 border-t border-hairline pt-4" onSubmit={send}>
        <label htmlFor="chat-input" className="sr-only">{t(locale, "chat_title")}</label>
        <Textarea
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send(e as unknown as React.FormEvent); }}
          placeholder={t(locale, "chat_placeholder")}
          className="min-h-[88px] resize-y rounded-lg border-hairline-strong bg-white p-3 text-[16px] leading-[1.6] text-ink shadow-none focus-visible:border-ink focus-visible:ring-0"
          spellCheck={false}
        />
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={busy || !draft.trim()} className="h-10 rounded-lg px-[18px] text-[14px] font-medium">{t(locale, "chat_send")}</Button>
          <span className="text-[13px] text-steel">{t(locale, "chat_helper")}</span>
        </div>
      </form>
    </div>
  );
}
