import Link from "next/link";
import { t, type Locale, type StringKey } from "@/lib/i18n";

/* 첫 화면 맨 위 — 마케터가 밈으로 할 수 있는 일 셋. 밈 목록(대시보드)은 그 아래 근거 화면이다.
   카드는 테두리만(칠하지 않는다) — 이 화면의 검정 버튼은 머리의 '추천받기' 하나로 둔다(한 화면 한 primary). */
type Tool = { href: string; title: StringKey; desc: StringKey };

export function MakeTools({ locale, regions }: { locale: Locale; regions: string[] }) {
  const q = regions.length ? `?regions=${regions.join(",")}` : "";
  const tools: Tool[] = [
    { href: `/recommend${q}`, title: "make_kit", desc: "make_kit_desc" },
    { href: `/briefing${q}`, title: "make_brief", desc: "make_brief_desc" },
    { href: `/check${regions[0] ? `?regions=${regions[0]}` : ""}`, title: "make_check", desc: "make_check_desc" },
  ];
  return (
    <section aria-labelledby="make-title" className="space-y-3">
      <h2 id="make-title" className="text-[15px] font-semibold text-ink">{t(locale, "make_title")}</h2>
      <ul className="grid gap-3 sm:grid-cols-3">
        {tools.map((tool) => (
          <li key={tool.title}>
            <Link href={tool.href} className="block h-full rounded-md border border-hairline-strong p-4 hover:border-ink focus-visible:border-ink">
              <span className="block text-[15px] font-semibold text-ink">{t(locale, tool.title)} <span aria-hidden>→</span></span>
              <span className="mt-1 block text-[13px] leading-[1.55] text-charcoal">{t(locale, tool.desc)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
