import { cn } from "@/lib/utils";

export type Tone = "neutral" | "good" | "caution" | "avoid" | "muted";

/* 상태 배지 — 글자 + 테두리만. 칸을 칠하지 않고 색만으로 구분하지 않는다(글자가 뜻을 말한다). */
export function StatusBadge({ tone = "neutral", children, className }: { tone?: Tone; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex h-[22px] shrink-0 items-center rounded border px-1.5 text-[12px] font-medium whitespace-nowrap",
      tone === "good" ? "border-good-line text-good"
        : tone === "caution" ? "border-caution-line text-caution"
          : tone === "avoid" ? "border-avoid-line text-avoid"
            : tone === "muted" ? "border-hairline text-steel" : "border-hairline-strong text-charcoal", className)}>
      {children}
    </span>
  );
}
