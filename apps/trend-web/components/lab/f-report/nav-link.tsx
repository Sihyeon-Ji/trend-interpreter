"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** 틀의 메뉴 한 칸 — 지금 화면이면 aria-current */
export function NavLink({ href, exact, children }: { href: string; exact?: boolean; children: React.ReactNode }) {
  const path = usePathname();
  const on = exact ? path === href : path === href || path.startsWith(`${href}/`);
  return <Link href={href} aria-current={on ? "page" : undefined}>{children}</Link>;
}
