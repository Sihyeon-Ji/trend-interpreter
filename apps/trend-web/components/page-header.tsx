import { cn } from "@/lib/utils";

/* 페이지 머리 — 모든 화면이 같은 순서: (경로) 제목 → 한 줄 설명, 오른쪽에 갱신 시각·보조 작업. 제목 위에 라벨을 얹지 않는다. */
export function PageHeader({ title, description, meta, actions, crumbs, children, divider = true }: {
  title: React.ReactNode; description?: React.ReactNode; meta?: React.ReactNode; actions?: React.ReactNode; crumbs?: React.ReactNode; children?: React.ReactNode;
  divider?: boolean;   // 아래에 탭(자기 밑줄이 있는)이 붙으면 끈다 — 선이 두 줄로 겹쳤다
}) {
  return (
    <header className={cn("space-y-4", divider && "border-b border-hairline pb-5")}>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div className="min-w-0 space-y-1.5">
          {crumbs && <div className="text-[13px] text-steel">{crumbs}</div>}
          <h1 className="text-[24px] leading-[1.3] font-semibold text-ink">{title}</h1>
          {description && <p className="max-w-[720px] text-[15px] leading-[1.55] text-charcoal">{description}</p>}
        </div>
        {(meta || actions) && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-steel">
            {meta}
            {actions}
          </div>
        )}
      </div>
      {children}
    </header>
  );
}
