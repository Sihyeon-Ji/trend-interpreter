"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { Locale } from "@/lib/i18n";
import { c } from "@/lib/lab/f-report-copy";

/** 틀의 찾기 칸. 리포트 화면의 목록을 거르고, 없으면 사전 전체 찾기로 넘긴다. 지역 선택은 그대로 둔다. */
export function SearchBox({ locale }: { locale: Locale }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = new URLSearchParams();
    const regions = sp.get("regions");
    if (regions) next.set("regions", regions);
    if (q.trim()) next.set("q", q.trim().slice(0, 60));
    router.push(`/lab/f-report${next.size ? `?${next}` : ""}`);
  };
  return (
    <form className="fr-search" role="search" onSubmit={submit}>
      <label htmlFor="fr-q" className="sr-only">{c(locale, "search_label")}</label>
      <svg width="15" height="15" viewBox="0 0 20 20" aria-hidden className="fr-steel"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M13 13l4.5 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
      <input id="fr-q" name="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder={c(locale, "search_placeholder")} autoComplete="off" />
      <button type="submit">{c(locale, "search_button")}</button>
    </form>
  );
}
