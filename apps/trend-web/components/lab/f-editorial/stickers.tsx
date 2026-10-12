import type { LabLocale as Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { fe, words } from "@/lib/lab/f-editorial/copy";
import { plainReason, type Reason } from "@/lib/lab/f-editorial";
import type { Diffusion, Lifecycle, RiskLevel } from "@/lib/contract/types";

export type Stageable = { lifecycle: Lifecycle; diffusion?: Diffusion | null; risk_level?: RiskLevel | null; risk_checked_at?: string | null };
// risk_human 은 Term 에서는 검수자가 정한 수준(문자열), 카드에는 없다 — 값이 있으면 '검수자가 정함' 으로만 본다
type Riskable = { risk_level?: RiskLevel | null; risk_checked_at?: string | null; risk_reasons?: string[] | null; risk_human?: unknown };

export type RiskKey = "caution" | "avoid" | "unknown" | "none";

/** 쓸 때 조심의 종류 — 주의·자제·보류·없음. 검사 전이면 null. */
export function riskKeyOf(item: Riskable): RiskKey | null {
  const r = riskOf(item);
  if (r) return r;
  return item.risk_level === "none" ? "none" : null;
}

/** 쓸 때 조심 아래 한 줄 — 주의·사용 자제·보류일 때. 규칙이 남긴 이유를 쉬운 문장으로 옮기고(인용·사이트 이름 없이), 모르는 꼴이면 일반 설명.
 *  검수자가 정한 수준이면 규칙의 이유를 붙이지 않는다 — 규칙이 반대로 보았을 수 있다. */
export function riskReasonText(item: Riskable, locale: Locale): Reason | null {
  const r = riskOf(item);
  if (!r) return null;
  if (item.risk_human) return { text: fe(locale, "risk_by_reviewer") };
  return plainReason(item.risk_reasons, locale) ?? { text: words(locale).riskWhy[r] };
}

export const lifecycleWord = (locale: Locale, lifecycle: Lifecycle | null | undefined) => words(locale).lifecycle[lifecycle ?? "unknown"] ?? String(lifecycle);
export const diffusionWord = (locale: Locale, diffusion: Diffusion | null | undefined) => (diffusion ? words(locale).diffusion[diffusion] : null);
export const riskLabel = (locale: Locale, key: RiskKey) => words(locale).risk[key];

/** 쓸 때 조심 한마디와 그 종류. 검사 전이면 null. */
export function riskWord(item: Riskable, locale: Locale): { key: RiskKey; label: string } | null {
  const key = riskKeyOf(item);
  return key ? { key, label: riskLabel(locale, key) } : null;
}

export const riskClass = (key: RiskKey | string) => (key === "caution" || key === "avoid" ? `fe-sticker fe-sticker--${key}` : "fe-sticker fe-sticker--muted");

/* 붙임표 — 칸마다 뜻 하나: 단계(생애주기), 퍼진 정도(full 일 때만), 쓸 때 조심. 꼭지 제목이 이미 단계를 말하면 hideStage 로 뺀다. */
export function Stickers({ item, locale, full = false, hideStage = false }: { item: Stageable; locale: Locale; full?: boolean; hideStage?: boolean }) {
  const risk = riskWord(item, locale);
  return (
    <span className="fe-stickers">
      {!hideStage && <span className="fe-sticker">{lifecycleWord(locale, item.lifecycle)}</span>}
      {full && item.diffusion && <span className={item.diffusion === "spreading" ? "fe-sticker fe-sticker--good" : "fe-sticker"}>{diffusionWord(locale, item.diffusion)}</span>}
      {risk && (full || risk.key !== "none") && <span className={riskClass(risk.key)}>{risk.label}</span>}
    </span>
  );
}
