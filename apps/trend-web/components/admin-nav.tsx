"use client";

import { usePathname } from "next/navigation";
import { ListTabs, type TabItem } from "@/components/list-tabs";

/** 관리 탭(검수·리스크·수집 현황). 현재 탭은 주소로 정한다 — 레이아웃은 탭을 옮겨도 다시 그리지 않는다. */
export function AdminNav({ items, label }: { items: TabItem[]; label: string }) {
  const path = usePathname();
  const current = (items.find((i) => i.href === path)
    ?? items.find((i) => i.href !== "/admin" && path.startsWith(`${i.href}/`)))?.id ?? items[0]?.id ?? "";
  return <ListTabs items={items} current={current} label={label} />;
}
