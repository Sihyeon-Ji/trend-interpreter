"use client";

import { useState } from "react";
import { t, type Locale } from "@/lib/i18n";
import { L } from "@/lib/labels";
import type { GenerationResult, SocialCopy } from "@/lib/types";

/** 복사 버튼. 클립보드를 쓸 수 없는 환경(권한 없음)이면 조용히 넘어간다 — 글은 화면에서 직접 고를 수 있다. */
function CopyButton({ text, locale }: { text: string; locale: Locale }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="text-[12px] text-link-blue hover:underline"
      onClick={() => { void navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }).catch(() => {}); }}>
      {done ? t(locale, "gen_copied") : t(locale, "gen_copy")}
    </button>
  );
}

const copyText = (c: SocialCopy) => [c.text, c.hashtags?.length ? c.hashtags.map((h) => `#${h}`).join(" ") : ""].filter(Boolean).join("\n\n");

/* 만든 결과물 (Plan 08). 사전 대조 검사를 통과한 안만 보이고, 뺀 안은 이유와 함께 알린다. */
export function GenerationView({ result, locale }: { result: GenerationResult; locale: Locale }) {
  const labels = L(locale);
  const card = "rounded-lg border border-hairline p-4";
  return (
    <section aria-labelledby="gen-title" className="space-y-4">
      <div>
        <h2 id="gen-title" className="text-[18px] font-semibold text-ink">{t(locale, "gen_title")}</h2>
        <p className="mt-0.5 text-[13px] text-steel">{t(locale, "gen_lang")}: {labels.draftLang[result.language] ?? result.language} · {result.memes.join(", ")}</p>
        <p className="mt-1 text-[13px] text-charcoal">{t(locale, "gen_draft_note")}</p>
        {result.source === "sample" && <p className="mt-1 text-[13px] text-steel">{t(locale, "gen_sample_note")}</p>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {result.copies.map((c, i) => (
          <article key={i} className={card}>
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="text-[13px] font-semibold text-ink">{t(locale, c.platform === "instagram" ? "gen_instagram" : "gen_x")}</h3>
              <CopyButton text={copyText(c)} locale={locale} />
            </div>
            <p className="mt-2 whitespace-pre-wrap text-[14px] leading-[1.6] text-ink">{c.text}</p>
            {c.hashtags && c.hashtags.length > 0 && <p className="mt-1 text-[13px] text-charcoal">{c.hashtags.map((h) => `#${h}`).join(" ")}</p>}
            {c.note_ko && <p className="mt-2 text-[12px] text-steel">{c.note_ko}</p>}
          </article>
        ))}
      </div>
      {result.script && (
        <article className={card}>
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-[13px] font-semibold text-ink">{t(locale, "gen_script")} · {result.script.title} <span className="font-normal text-steel">({result.script.duration_s}s)</span></h3>
            <CopyButton locale={locale} text={result.script.scenes.map((s) => `${s.start_s}–${s.end_s}s  ${s.visual} / ${s.caption ?? ""}${s.line ? ` / ${s.line}` : ""}`).join("\n")} />
          </div>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-[13px]">
              <thead className="border-b border-hairline text-steel">
                <tr><th className="py-1.5 pr-3 font-medium">s</th><th className="py-1.5 pr-3 font-medium">{t(locale, "gen_scene_visual")}</th><th className="py-1.5 pr-3 font-medium">{t(locale, "gen_scene_caption")}</th><th className="py-1.5 font-medium">{t(locale, "gen_scene_line")}</th></tr>
              </thead>
              <tbody className="divide-y divide-hairline-soft align-top">
                {result.script.scenes.map((s, i) => (
                  <tr key={i}><td className="py-1.5 pr-3 whitespace-nowrap tabular-nums text-steel">{s.start_s}–{s.end_s}</td><td className="py-1.5 pr-3 text-ink">{s.visual}</td><td className="py-1.5 pr-3 text-ink">{s.caption}</td><td className="py-1.5 text-ink">{s.line}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.script.note_ko && <p className="mt-2 text-[12px] text-steel">{result.script.note_ko}</p>}
        </article>
      )}
      {result.thumbnail && (
        <article className={card}>
          <h3 className="text-[13px] font-semibold text-ink">{t(locale, "gen_thumbnail")}</h3>
          <dl className="mt-2 grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-[13px]">
            <dt className="text-steel">{t(locale, "gen_thumb_headline")}</dt><dd className="text-ink">{result.thumbnail.headline}</dd>
            <dt className="text-steel">{t(locale, "gen_thumb_layout")}</dt><dd className="text-ink">{result.thumbnail.layout}</dd>
            {result.thumbnail.colors && result.thumbnail.colors.length > 0 && <><dt className="text-steel">{t(locale, "gen_thumb_colors")}</dt><dd className="text-ink">{result.thumbnail.colors.join(", ")}</dd></>}
            {result.thumbnail.subject && <><dt className="text-steel">{t(locale, "gen_thumb_subject")}</dt><dd className="text-ink">{result.thumbnail.subject}</dd></>}
          </dl>
        </article>
      )}
      {result.dropped.length > 0 && (
        <div className="text-[13px] text-charcoal">
          <p className="text-steel">{t(locale, "gen_dropped")} {result.dropped.length}</p>
          {/* 이유는 한국어로 남는다(규칙·검사 문장) — 영어 화면에는 건수만 */}
          {locale === "ko" && <ul className="mt-1 list-disc pl-4">{result.dropped.map((d) => <li key={d.id}>{d.reason}</li>)}</ul>}
        </div>
      )}
    </section>
  );
}
