"use client";

import type { LabLocale as Locale } from "@/lib/i18n";
import { c } from "@/lib/lab/f-report/copy";
import { useWatchlist, type WatchItem } from "./watch";

export function WatchButton({ item, locale, small }: { item: Omit<WatchItem, "at">; locale: Locale; small?: boolean }) {
  const { has, toggle } = useWatchlist();
  const on = has(item.id);
  return (
    <button type="button" className={`fr-btn${small ? " fr-btn-sm" : ""}${on ? " is-on" : ""}`} aria-pressed={on} onClick={() => toggle(item)}
      title={on ? c(locale, "unwatch") : c(locale, "watch")}>
      <span aria-hidden>{on ? "★" : "☆"}</span> {on ? c(locale, "watched") : c(locale, "watch")}
    </button>
  );
}
