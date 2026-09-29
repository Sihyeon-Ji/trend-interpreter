import { StatusBadge } from "@/components/status-badge";
import { t, type Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { L } from "@/lib/labels";
import type { Diffusion, Lifecycle, RiskLevel } from "@/lib/contract/types";

/* 단계·쓸 때 조심 칸 — 대시보드 표, 사전 항목 요약, 나라 화면이 같은 말을 쓰게 한 곳에 둔다(검토: 같은 밈을 화면마다 다르게 불렀다). */
const DIFF_TONE = { spreading: "good", underground: "good", mainstream: "neutral", fading: "muted" } as const;

export function StageCell({ diffusion, lifecycle, locale }: { diffusion?: Diffusion | null; lifecycle: Lifecycle; locale: Locale }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      {diffusion && <StatusBadge tone={DIFF_TONE[diffusion]}>{t(locale, `diffusion_${diffusion}`)}</StatusBadge>}
      <span className="text-[13px] text-charcoal">{L(locale).lifecycle[lifecycle]}</span>
    </span>
  );
}

type RiskInput = { risk_level?: RiskLevel | null; risk_checked_at?: string | null };

/** 쓸 때 조심 — 주의·사용 자제·근거 부족은 배지, 문제가 없으면 '특이 사항 없음', 아직 검사 전이면 '확인 전'. */
export function RiskCell({ item, locale, why = false }: { item: RiskInput; locale: Locale; why?: boolean }) {
  const r = riskOf(item);
  const reason = (key: "risk_caution_why" | "risk_avoid_why" | "risk_unknown_why" | "risk_none_why") =>
    why ? <span className="mt-1 block text-[13px] leading-[1.5] text-steel">{t(locale, key)}</span> : null;
  if (r) {
    return (
      <span>
        <StatusBadge tone={r === "avoid" ? "avoid" : r === "caution" ? "caution" : "muted"}>{t(locale, `risk_${r}`)}</StatusBadge>
        {reason(`risk_${r}_why`)}
      </span>
    );
  }
  if (item.risk_level === "none") return <span className="text-[13px] text-charcoal">{t(locale, "risk_none_short")}{reason("risk_none_why")}</span>;
  return <span className="text-[13px] text-steel">{t(locale, "risk_not_checked")}</span>;
}
