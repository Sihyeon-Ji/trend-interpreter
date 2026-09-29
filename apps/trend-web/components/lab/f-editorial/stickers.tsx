import type { Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { fe, words } from "@/lib/lab/f-editorial-copy";
import { cleanReason } from "@/lib/lab/f-editorial";
import type { Diffusion, Lifecycle, RiskLevel } from "@/lib/contract/types";

type Stageable = { lifecycle: Lifecycle; diffusion?: Diffusion | null; risk_level?: RiskLevel | null; risk_checked_at?: string | null };
// risk_human 은 Term 에서는 검수자가 정한 수준(문자열), 카드에는 없다 — 값이 있으면 '검수자가 정함' 으로만 본다
type Riskable = { risk_level?: RiskLevel | null; risk_checked_at?: string | null; risk_reasons?: string[] | null; risk_human?: unknown };

/** 쓸 때 조심 아래 한 줄 — 주의·사용 자제일 때만. 한국어 화면은 규칙이 남긴 실제 이유(인용은 뗀다), 영어 화면은 일반 설명(이유가 한국어뿐이다).
 *  검수자가 정한 수준이면 규칙의 이유를 붙이지 않는다 — 규칙이 반대로 보았을 수 있다. */
export function riskReasonText(item: Riskable, locale: Locale): string | null {
  const r = riskOf(item);
  if (r !== "caution" && r !== "avoid") return null;
  if (item.risk_human) return fe(locale, "risk_by_reviewer");
  const own = (item.risk_reasons ?? []).find((x) => x !== "검수자가 정한 수준");
  const cleaned = own ? cleanReason(own) : "";
  return locale === "ko" && cleaned ? cleaned : words(locale).riskWhy[r];
}

/** 단계 한마디 — 퍼진 정도가 있으면 그것, 없으면 생애주기 */
export function stageWord(item: Stageable, locale: Locale): string {
  const w = words(locale);
  return item.diffusion ? w.diffusion[item.diffusion] : w.lifecycle[item.lifecycle];
}

/** 쓸 때 조심 한마디와 그 종류. 검사 전이면 null. */
export function riskWord(item: Stageable, locale: Locale): { key: "caution" | "avoid" | "unknown" | "none"; label: string } | null {
  const r = riskOf(item);
  if (r) return { key: r, label: words(locale).risk[r] };
  if (item.risk_level === "none") return { key: "none", label: words(locale).risk.none };
  return null;
}

const riskClass = (key: string) => (key === "unknown" ? "fe-sticker fe-sticker--muted" : key === "none" ? "fe-sticker fe-sticker--muted" : `fe-sticker fe-sticker--${key}`);

/* 붙임표 — 단계(퍼진 정도)와 쓸 때 조심. full 이면 생애주기와 '주의점 없음' 까지 다 붙인다(표지·항목). */
export function Stickers({ item, locale, full = false }: { item: Stageable; locale: Locale; full?: boolean }) {
  const w = words(locale);
  const risk = riskWord(item, locale);
  const diffusionClass = item.diffusion === "spreading" ? "fe-sticker fe-sticker--good" : item.diffusion === "fading" ? "fe-sticker fe-sticker--muted" : "fe-sticker";
  return (
    <span className="fe-stickers">
      {full && <span className="fe-sticker">{w.lifecycle[item.lifecycle]}</span>}
      {item.diffusion ? <span className={diffusionClass}>{w.diffusion[item.diffusion]}</span> : !full && <span className="fe-sticker">{w.lifecycle[item.lifecycle]}</span>}
      {risk && (full || risk.key !== "none") && <span className={riskClass(risk.key)}>{risk.label}</span>}
    </span>
  );
}
