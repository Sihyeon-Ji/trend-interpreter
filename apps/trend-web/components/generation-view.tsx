"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/status-badge";
import { RiskCell, StageCell } from "@/components/term-status";
import { t, type Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { L, fmtDate, regionLabel, sourceName } from "@/lib/labels";
import type { GenerationResult, RecommendItem, ScriptScene, SocialCopy, ThumbnailPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

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
    <span className="shrink-0 text-right">
      <Button type="button" variant="outline" aria-label={`${t(locale, "gen_copy")}: ${label}`} onClick={copy}
        className="h-10 rounded-md px-3 text-[13px] sm:h-8">
        {state === "done" ? t(locale, "gen_copied") : t(locale, "gen_copy")}
      </Button>
      <span role="status" className={state === "failed" ? "mt-1 block max-w-[220px] text-[12px] text-error" : "sr-only"}>
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
const seconds = (locale: Locale, s: ScriptScene) => t(locale, "gen_seconds").replace("{a}", String(s.start_s)).replace("{b}", String(s.end_s));

/** '밈을 쓴 방식' — 모델이 쓴 설명(화면 언어). 결과물 글과 떨어뜨려 라벨을 붙인다. */
function How({ note, locale }: { note?: string | null; locale: Locale }) {
  if (!note) return null;
  return <p className="mt-2 text-[13px] leading-[1.5] text-charcoal"><span className="text-steel">{t(locale, "gen_how")}</span> {note}</p>;
}

/** 탭 하나 안의 안들 — '안 1' 소제목과 오른쪽 복사 버튼, 본문(결과물의 말로 lang), 해시태그, 쓴 방식. 안 사이는 가는 선. */
function Drafts({ copies, platform, lang, locale }: { copies: SocialCopy[]; platform: string; lang?: string; locale: Locale }) {
  return (
    <ul className="divide-y divide-hairline">
      {copies.map((c, i) => {
        const option = t(locale, "gen_option").replace("{n}", String(i + 1));
        return (
          <li key={i} className="py-4 first:pt-3">
            <div className="flex items-start justify-between gap-3">
              <h3 className="pt-1.5 text-[14px] font-semibold text-ink">{option}</h3>
              <CopyButton text={copyText(c)} label={`${platform} ${i + 1}`} locale={locale} />
            </div>
            <p lang={lang} className="mt-2 text-[15px] leading-[1.6] whitespace-pre-wrap text-ink">{c.text}</p>
            {c.hashtags && c.hashtags.length > 0 && <p lang={lang} className="mt-1 text-[14px] text-charcoal">{c.hashtags.map((h) => `#${h}`).join(" ")}</p>}
            <How note={c.note_ko} locale={locale} />
          </li>
        );
      })}
    </ul>
  );
}

/* 만든 결과물 (Plan 08). 규칙 검사를 통과한 안만 보이고, 뺀 안은 이유와 함께 알린다.
   검정 버튼은 두지 않는다 — 복사·다시 만들기·밈 다시 고르기 모두 테두리 버튼(이 단계에는 '다음 행동' 이 없다). */
export function GenerationView({ result, locale, used, changed, onRepick, onRemake }: {
  result: GenerationResult; locale: Locale; used: RecommendItem[]; changed: boolean; onRepick: () => void; onRemake: () => void;
}) {
  const labels = L(locale);
  const lang = langTag(result.language);
  const insta = result.copies.filter((c) => c.platform === "instagram");
  const x = result.copies.filter((c) => c.platform === "x");
  const tabs = [
    insta.length ? { id: "instagram", label: t(locale, "gen_instagram"), count: insta.length } : null,
    x.length ? { id: "x", label: t(locale, "gen_x"), count: x.length } : null,
    result.script ? { id: "script", label: t(locale, "gen_script") } : null,
    result.thumbnail ? { id: "thumbnail", label: t(locale, "gen_thumbnail") } : null,
  ].filter((v): v is { id: string; label: string; count?: number } => !!v);
  const sample = result.source === "sample";
  const pair = "flex gap-2";
  return (
    <section aria-labelledby="gen-title" className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        {/* 결과가 오면 여기로 초점을 옮긴다(recommend-form) — 긴 생성 뒤 어디에 무엇이 생겼는지 알린다 */}
        <h2 id="gen-title" tabIndex={-1} className="flex scroll-mt-20 items-center gap-2 text-[18px] font-semibold text-ink outline-none">
          {t(locale, "gen_title")}
          {sample && <StatusBadge tone="muted">{t(locale, "rec_sample_badge")}</StatusBadge>}
        </h2>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" className="h-10 rounded-md px-4 text-[14px]" onClick={onRepick}>{t(locale, "gen_repick")}</Button>
          <Button type="button" variant="outline" className="h-10 rounded-md px-4 text-[14px]" onClick={onRemake}>{t(locale, "gen_remake")}</Button>
        </div>
      </div>
      {changed && <p className="text-[13px] text-charcoal">{t(locale, "gen_changed")}</p>}
      <dl className="flex flex-wrap gap-x-8 gap-y-1 text-[14px]">
        <div className={pair}><dt className="text-steel">{t(locale, "gen_region_short")}</dt><dd className="text-ink">{regionLabel(locale, result.region)}</dd></div>
        <div className={pair}><dt className="text-steel">{t(locale, "gen_lang")}</dt><dd className="text-ink">{labels.draftLang[result.language] ?? result.language}</dd></div>
        <div className={pair}><dt className="text-steel">{t(locale, "rec_tone")}</dt><dd className="text-ink">{labels.campaignTone[result.tone]}</dd></div>
      </dl>
      <div className="space-y-1 text-[13px] leading-[1.5]">
        <p className="text-charcoal">{t(locale, "gen_draft_note")}</p>
        {sample && <p className="text-steel">{t(locale, "gen_sample_note")}</p>}
      </div>

      {used.length > 0 && (
        <div>
          <table className="w-full border-collapse text-left text-[13px]">
            <caption className="sr-only">{t(locale, "gen_used")}</caption>
            <thead>
              <tr className="border-b border-hairline text-steel">
                <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "gen_used")}</th>
                <th scope="col" className="hidden py-2 pr-3 font-medium sm:table-cell">{t(locale, "rec_stage")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "rec_care")}</th>
                <th scope="col" className="hidden py-2 font-medium sm:table-cell">{t(locale, "rec_sources")}</th>
              </tr>
            </thead>
            <tbody>
              {used.map((it) => (
                <tr key={it.term_id} className="border-b border-hairline align-top">
                  <td className="py-2 pr-3"><span lang={langTag(it.lang)} className="text-[14px] font-semibold text-ink">{it.canonical}</span></td>
                  <td className="hidden py-2 pr-3 sm:table-cell"><StageCell diffusion={it.diffusion} lifecycle={it.lifecycle} locale={locale} /></td>
                  <td className="py-2 pr-3"><RiskCell item={it} locale={locale} /></td>
                  <td className="hidden py-2 sm:table-cell">
                    {it.evidences[0] ? (
                      <a href={it.evidences[0].url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">
                        {sourceName(locale, it.evidences[0].source_domain)}<span className="sr-only"> {t(locale, "rec_new_tab")}</span>
                        <span className="ml-1.5 text-[12px] text-steel tabular-nums">{fmtDate(it.evidences[0].observed_at)}</span>
                      </a>
                    ) : <span className="text-steel">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tabs.length > 0 && (
        <Tabs defaultValue={tabs[0].id} className="gap-0">
          {/* 휴대폰에서는 탭 줄을 옆으로 밀어 본다 — 페이지 자체는 옆으로 밀리지 않는다 */}
          <div className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0">
            <TabsList variant="line" aria-label={t(locale, "gen_kinds")}
              className="w-full min-w-max justify-start gap-6 rounded-none border-b border-hairline p-0 group-data-horizontal/tabs:h-11">
              {tabs.map((tab) => (
                <TabsTrigger key={tab.id} value={tab.id}
                  className="h-11 flex-none rounded-none border-0 px-0 text-[15px] font-normal text-charcoal hover:text-ink data-active:font-semibold data-active:text-ink after:bg-ink group-data-horizontal/tabs:after:bottom-[-1px]">
                  {tab.label}
                  {tab.count != null && <span className="text-[13px] font-normal text-steel tabular-nums">{tab.count}</span>}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {insta.length > 0 && <TabsContent value="instagram"><Drafts copies={insta} platform={t(locale, "gen_instagram")} lang={lang} locale={locale} /></TabsContent>}
          {x.length > 0 && <TabsContent value="x"><Drafts copies={x} platform={t(locale, "gen_x")} lang={lang} locale={locale} /></TabsContent>}
          {result.script && (
            <TabsContent value="script" className="pt-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 lang={lang} className="text-[15px] font-semibold text-ink">{result.script.title}</h3>
                  <p className="mt-0.5 text-[13px] text-steel tabular-nums">{t(locale, "gen_length").replace("{n}", String(result.script.duration_s))}</p>
                </div>
                <CopyButton locale={locale} label={t(locale, "gen_script")}
                  text={result.script.scenes.map((s) => [seconds(locale, s), s.visual, s.caption, s.line].filter(Boolean).join(" / ")).join("\n")} />
              </div>
              {/* md 이상은 칸 너비를 정한 표, 휴대폰은 장면마다 블록 — 표가 잘리고 대사 칸이 보이지 않았다 */}
              <table className="mt-3 hidden w-full table-fixed border-collapse text-left text-[14px] md:table">
                <thead>
                  <tr className="border-b border-hairline text-[13px] text-steel">
                    <th scope="col" className="w-[88px] py-2 pr-3 font-medium">{t(locale, "gen_time")}</th>
                    <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "gen_scene_visual")}</th>
                    <th scope="col" className="py-2 pr-3 font-medium">{t(locale, "gen_scene_caption")}</th>
                    <th scope="col" className="py-2 font-medium">{t(locale, "gen_scene_line")}</th>
                  </tr>
                </thead>
                <tbody lang={lang} className="align-top">
                  {result.script.scenes.map((s, i) => (
                    <tr key={i} className="border-b border-hairline">
                      <td lang={locale} className="py-2 pr-3 whitespace-nowrap text-steel tabular-nums">{seconds(locale, s)}</td>
                      <td className="py-2 pr-3 text-ink">{s.visual || "—"}</td>
                      <td className="py-2 pr-3 text-ink">{s.caption || "—"}</td>
                      <td className="py-2 text-ink">{s.line || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ol className="mt-3 divide-y divide-hairline border-y border-hairline md:hidden">
                {result.script.scenes.map((s, i) => (
                  <li key={i} className="py-3">
                    <h4 className="text-[13px] font-medium text-steel tabular-nums">{seconds(locale, s)}</h4>
                    <dl className="mt-1.5 grid grid-cols-[48px_minmax(0,1fr)] gap-x-3 gap-y-1 text-[14px]">
                      {([["gen_scene_visual", s.visual], ["gen_scene_caption", s.caption], ["gen_scene_line", s.line]] as const).filter(([, v]) => v).map(([k, v]) => (
                        <div key={k} className="contents">
                          <dt className="text-[13px] text-steel">{t(locale, k)}</dt><dd lang={lang} className="text-ink">{v}</dd>
                        </div>
                      ))}
                    </dl>
                  </li>
                ))}
              </ol>
              <How note={result.script.note_ko} locale={locale} />
            </TabsContent>
          )}
          {result.thumbnail && (
            <TabsContent value="thumbnail" className="pt-3">
              <div className="flex items-start justify-between gap-3">
                <h3 className="pt-1.5 text-[14px] font-semibold text-ink">{t(locale, "gen_thumbnail")}</h3>
                <CopyButton locale={locale} label={t(locale, "gen_thumbnail")} text={thumbText(result.thumbnail, locale)} />
              </div>
              <dl className="mt-2 grid grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-[14px]">
                <dt className="text-steel">{t(locale, "gen_thumb_headline")}</dt><dd lang={lang} className="text-ink">{result.thumbnail.headline}</dd>
                {/* 설명 칸은 화면 언어가 아니면 백엔드가 비운다 — 빈 칸은 그리지 않는다 */}
                {result.thumbnail.layout && <><dt className="text-steel">{t(locale, "gen_thumb_layout")}</dt><dd className="text-ink">{result.thumbnail.layout}</dd></>}
                {result.thumbnail.colors && result.thumbnail.colors.length > 0 && <><dt className="text-steel">{t(locale, "gen_thumb_colors")}</dt><dd className="text-ink">{result.thumbnail.colors.join(", ")}</dd></>}
                {result.thumbnail.subject && <><dt className="text-steel">{t(locale, "gen_thumb_subject")}</dt><dd className="text-ink">{result.thumbnail.subject}</dd></>}
              </dl>
            </TabsContent>
          )}
        </Tabs>
      )}

      {result.dropped.length > 0 && (
        <div className={cn("text-[13px] text-charcoal", tabs.length && "border-t border-hairline pt-3")}>
          <p className="text-steel">{t(locale, "gen_dropped").replace("{n}", String(result.dropped.length))}</p>
          {/* 뺀 까닭은 규칙의 코드로 온다 — 두 언어 모두 그대로 보인다 */}
          <ul className="mt-1 list-disc pl-4">{result.dropped.map((d) => <li key={d.id}>{t(locale, `gen_drop_${d.code}`)}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
