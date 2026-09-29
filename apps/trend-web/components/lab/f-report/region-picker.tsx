"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { Locale } from "@/lib/i18n";
import { c, REGIONS, regionName } from "@/lib/lab/f-report-copy";

/** 지역 여러 곳 고르기 — 주소(?regions=KR,JP)가 곧 상태. 검색어는 지우고(다른 목록이므로) 쪽은 1로. */
export function RegionPicker({ locale, selected, counts }: { locale: Locale; selected: string[]; counts: Record<string, number> }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [pending, start] = useTransition();
  const go = (next: string[]) => {
    const p = new URLSearchParams();
    if (next.length) p.set("regions", next.join(","));
    const q = sp.get("q");
    if (q) p.set("q", q);
    start(() => router.push(`/lab/f-report${p.size ? `?${p}` : ""}`, { scroll: false }));
  };
  const toggle = (r: string) => go(selected.includes(r) ? selected.filter((x) => x !== r) : [...selected, r].sort((a, b) => REGIONS.indexOf(a) - REGIONS.indexOf(b)));
  return (
    <div className={`fr-chips${pending ? " fr-pending" : ""}`} role="group" aria-label={c(locale, "regions_label")} aria-busy={pending}>
      <button type="button" className="fr-chip" aria-pressed={selected.length === 0} onClick={() => go([])}>
        {c(locale, "regions_clear")} <small className="fr-num">{counts.ALL ?? ""}</small>
      </button>
      {REGIONS.map((r) => {
        const n = counts[r] ?? 0;
        return (
          <button key={r} type="button" className={`fr-chip${n === 0 ? " is-zero" : ""}`} aria-pressed={selected.includes(r)} onClick={() => toggle(r)}>
            {regionName(locale, r)} <small className="fr-num">{n}</small>
          </button>
        );
      })}
    </div>
  );
}
