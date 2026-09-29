import { cn } from "@/lib/utils";

/* 고르는 칩(지역·톤·분류)의 모양 — 한 곳에서. 선택은 파랑 테두리 + 먹 글자로 보인다. 검정으로 칠하는 것은 화면의 주요 버튼 하나뿐이다
   (docs/트렌드/디자인-개편.md 원칙 3, 개편 검토: 선택 칩까지 검정이라 주요 버튼이 묻혔다). 모서리 6px, 높이 32px(휴대폰 40px). */
export const chipClass = (on: boolean) =>
  cn("inline-flex h-10 items-center gap-1.5 rounded-md border px-3 text-[13px] whitespace-nowrap sm:h-8",
    on ? "border-link-blue bg-background font-medium text-ink shadow-[inset_0_0_0_1px_var(--link-blue)]"
      : "border-hairline-strong bg-background text-charcoal hover:border-ink hover:text-ink");
