"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { Locale } from "@/lib/i18n";
import { c, REGIONS, regionName, regionsParam } from "@/lib/lab/f-report/copy";

/** 시장 여러 곳 고르기 — 주소(?regions=KR,JP)가 곧 상태. 한국이 기본값이라 주소에서 비우고, 아무것도 안 고르면 'all'(모든 시장). 쪽은 1로. */
export function RegionPicker({ locale, selected, counts }: { locale: Locale; selected: string[]; counts: Record<string, number> }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [pending, start] = useTransition();
  const go = (next: string[]) => {
    const p = new URLSearchParams();
    const v = regionsParam(next);
    if (v) p.set("regions", v);
    const q = sp.get("q");
    if (q) p.set("q", q);
    start(() => router.push(`/lab/f-report${p.size ? `?${p}` : ""}`, { scroll: false }));
  };
  const toggle = (r: string) => go(selected.includes(r) ? selected.filter((x) => x !== r) : [...selected, r].sort((a, b) => REGIONS.indexOf(a) - REGIONS.indexOf(b)));
  return (
    <div className={`fr-chips${pending ? " fr-pending" : ""}`} role="group" aria-label={c(locale, "regions_label")} aria-busy={pending}>
      <button type="button" className="fr-chip" aria-pressed={selected.length === 0} onClick={() => go([])}>
        {c(locale, "regions_all")} <small className="fr-num">{counts.ALL ?? ""}</small>
      </button>
      {REGIONS.map((r) => {
        const n = counts[r] ?? 0;
        return (
          <button key={r} type="button" className={`fr-chip${n === 0 ? " is-zero" : ""}`} aria-pressed={selected.includes(r)} onClick={() => toggle(r)}>
            {r === "GLOBAL" ? c(locale, "region_global") : regionName(locale, r)} <small className="fr-num">{n}</small>
          </button>
        );
      })}
    </div>
  );
}
