import Link from "next/link";
import { cn } from "@/lib/utils";

export type TabItem = { id: string; label: string; count?: number; href: string };

/* 주소가 바뀌는 탭(서버 화면). 밑줄로 현재 탭을 보이고 건수를 이름 옆에 둔다. 휴대폰에서는 옆으로 밀어 본다. */
export function ListTabs({ items, current, label }: { items: TabItem[]; current: string; label: string }) {
  return (
    <nav aria-label={label} className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0">
      <ul className="flex min-w-max gap-6 border-b border-hairline">
        {items.map((i) => {
          const on = i.id === current;
          return (
            <li key={i.id}>
              <Link href={i.href} scroll={false} aria-current={on ? "page" : undefined}
                className={cn("-mb-px inline-flex h-11 items-center gap-1.5 border-b-2 text-[15px] whitespace-nowrap",
                  on ? "border-ink font-semibold text-ink" : "border-transparent text-charcoal hover:text-ink")}>
                {i.label}
                {i.count != null && <span className={cn("tabular-nums text-[13px]", on ? "text-charcoal" : "text-steel")}>{i.count}</span>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
