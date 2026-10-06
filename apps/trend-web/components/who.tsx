import type { Locale } from "@/lib/i18n";
import { t } from "@/lib/i18n";

/** 누가 정했나 — 규칙(실선)·모델(점선)·사람(서명 잉크로 채움). 화면의 판단마다 붙인다(Plan 20, 시안 n-redesign).
 *  색에만 기대지 않게 선 모양과 낱말이 함께 다르다. 스타일은 ledger.css 의 .n-who. */
export type WhoKind = "rule" | "model" | "human" | "wait";

export function Who({ kind, locale, children }: { kind: WhoKind; locale: Locale; children?: React.ReactNode }) {
  return <span className="n-who" data-who={kind}>{children ?? t(locale, `who_${kind}`)}</span>;
}
