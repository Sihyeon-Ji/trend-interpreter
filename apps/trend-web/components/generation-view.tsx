"use client";

import { useState } from "react";
import { t, type Locale } from "@/lib/i18n";
import { L } from "@/lib/labels";
import type { GenerationResult, SocialCopy, ThumbnailPlan } from "@/lib/types";

/** 복사 버튼. 버튼마다 무엇을 복사하는지 이름을 붙이고(화면 읽기 프로그램에서 '복사' 여섯 개가 구별되지 않았다), 결과를 알린다.
 *  클립보드를 쓸 수 없으면(권한 없음·http) 직접 고르라고 알린다 — 조용히 넘어가면 복사된 줄 알았다(검토 3차). */
function CopyButton({ text, label, locale }: { text: string; label: string; locale: Locale }) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");
  const copy = () => {
    const done = (s: "done" | "failed") => { setState(s); setTimeout(() => setState("idle"), s === "done" ? 1500 : 4000); };
    if (!navigator.clipboard) { done("failed"); return; }
    navigator.clipboard.writeText(text).then(() => done("done"), () => done("failed"));
  };
  return (
    <span className="text-right">
      <button type="button" aria-label={`${t(locale, "gen_copy")}: ${label}`} className="text-[12px] text-link-blue hover:underline" onClick={copy}>
        {state === "done" ? t(locale, "gen_copied") : t(locale, "gen_copy")}
      </button>
      <span role="status" className={state === "failed" ? "block text-[12px] text-error" : "sr-only"}>
        {state === "failed" ? t(locale, "gen_copy_failed") : state === "done" ? t(locale, "gen_copied") : ""}
      </span>
    </span>
  );
}

// 백엔드 pipeline/generate.copy_text 와 같은 글 — X 글자 수 검사가 이 글을 잰다
const copyText = (c: SocialCopy) => [c.text, c.hashtags?.length ? c.hashtags.map((h) => `#${h}`).join(" ") : ""].filter(Boolean).join("\n\n");
const thumbText = (th: ThumbnailPlan, locale: Locale) =>
  [[t(locale, "gen_thumb_headline"), th.headline], [t(locale, "gen_thumb_layout"), th.layout], [t(locale, "gen_thumb_colors"), (th.colors ?? []).join(", ")],
   [t(locale, "gen_thumb_subject"), th.subject]].filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join("\n");

/* 만든 결과물 (Plan 08). 규칙 검사를 통과한 안만 보이고, 뺀 안은 이유와 함께 알린다. */
export function GenerationView({ result, locale }: { result: GenerationResult; locale: Locale }) {
  const labels = L(locale);
  const card = "rounded-lg border border-hairline p-4";
  // 카드 제목 — 플랫폼마다 번호를 붙인다(복사 버튼 이름에도 쓴다)
  const seen: Record<string, number> = {};
  const titles = result.copies.map((c) => `${t(locale, c.platform === "instagram" ? "gen_instagram" : "gen_x")} ${(seen[c.platform] = (seen[c.platform] ?? 0) + 1)}`);
  return (
    <section aria-labelledby="gen-title" className="space-y-4">
      <div>
        {/* 결과가 오면 여기로 초점을 옮긴다(recommend-form) — 긴 생성 뒤 어디에 무엇이 생겼는지 알린다 */}
        <h2 id="gen-title" tabIndex={-1} className="text-[18px] font-semibold text-ink outline-none">{t(locale, "gen_title")}</h2>
        <p className="mt-0.5 text-[13px] text-steel">{t(locale, "gen_lang")}: {labels.draftLang[result.language] ?? result.language} · {result.memes.join(", ")}</p>
        <p className="mt-1 text-[13px] text-charcoal">{t(locale, "gen_draft_note")}</p>
        {result.source === "sample" && <p className="mt-1 text-[13px] text-steel">{t(locale, "gen_sample_note")}</p>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {result.copies.map((c, i) => (
          <article key={i} className={card}>
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="text-[13px] font-semibold text-ink">{titles[i]}</h3>
              <CopyButton text={copyText(c)} label={titles[i]} locale={locale} />
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
            <CopyButton locale={locale} label={t(locale, "gen_script")} text={result.script.scenes.map((s) => `${s.start_s}–${s.end_s}s  ${s.visual} / ${s.caption ?? ""}${s.line ? ` / ${s.line}` : ""}`).join("\n")} />
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
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-[13px] font-semibold text-ink">{t(locale, "gen_thumbnail")}</h3>
            <CopyButton locale={locale} label={t(locale, "gen_thumbnail")} text={thumbText(result.thumbnail, locale)} />
          </div>
          <dl className="mt-2 grid grid-cols-[110px_1fr] gap-x-3 gap-y-1 text-[13px]">
            <dt className="text-steel">{t(locale, "gen_thumb_headline")}</dt><dd className="text-ink">{result.thumbnail.headline}</dd>
            {/* 설명 칸은 화면 언어가 아니면 백엔드가 비운다 — 빈 칸은 그리지 않는다 */}
            {result.thumbnail.layout && <><dt className="text-steel">{t(locale, "gen_thumb_layout")}</dt><dd className="text-ink">{result.thumbnail.layout}</dd></>}
            {result.thumbnail.colors && result.thumbnail.colors.length > 0 && <><dt className="text-steel">{t(locale, "gen_thumb_colors")}</dt><dd className="text-ink">{result.thumbnail.colors.join(", ")}</dd></>}
            {result.thumbnail.subject && <><dt className="text-steel">{t(locale, "gen_thumb_subject")}</dt><dd className="text-ink">{result.thumbnail.subject}</dd></>}
          </dl>
        </article>
      )}
      {result.dropped.length > 0 && (
        <div className="text-[13px] text-charcoal">
          <p className="text-steel">{t(locale, "gen_dropped")} {result.dropped.length}</p>
          {/* 뺀 까닭은 규칙의 코드로 온다 — 두 언어 모두 그대로 보인다 */}
          <ul className="mt-1 list-disc pl-4">{result.dropped.map((d) => <li key={d.id}>{t(locale, `gen_drop_${d.code}`)}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
