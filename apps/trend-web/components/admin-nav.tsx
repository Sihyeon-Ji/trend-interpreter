"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/admin", label: "검수" },
  { href: "/admin/risk", label: "주의 표현" },
  { href: "/admin/status", label: "수집 현황" },
];

export function AdminNav() {
  const path = usePathname();
  return (
    <nav className="flex gap-5 border-b border-hairline text-[14px]">
      {LINKS.map((l) => {
        const active = path === l.href;
        return (
          <Link key={l.href} href={l.href} className={cn("-mb-px border-b-2 py-2", active ? "border-ink font-medium text-ink" : "border-transparent text-steel hover:text-ink")}>
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
