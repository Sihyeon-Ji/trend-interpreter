"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import type { Locale } from "@/lib/i18n";
import { BASE, copy, editionName } from "@/lib/lab/o-editorial";

const noop = () => () => {};
const readLocale = (): Locale => (document.documentElement.lang === "en" ? "en" : "ko");

export default function EntryError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const locale = useSyncExternalStore(noop, readLocale, (): Locale => "ko");
  const c = copy(locale);
  return (
    <div className="oe-wrap" style={{ paddingBlock: 48 }}>
      <div className="oe-state" role="alert">
        <p>{c.entryFailed}</p>
        <p style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 10 }}>
          <button type="button" className="oe-btn oe-btn-line" onClick={() => retry()}>{c.retry}</button>
          <Link href={BASE} className="oe-btn oe-btn-line">{c.backTo(editionName(locale, "KR"))}</Link>
        </p>
      </div>
    </div>
  );
}
