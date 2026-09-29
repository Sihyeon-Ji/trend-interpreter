"use client";

import type { Locale } from "@/lib/i18n";
import { WatchButton } from "./board";
import { useWatchlist } from "./store";

/** 항목 화면의 '지켜보기' — 리포트의 '지켜보는 밈' 탭에 모인다(이 브라우저에만) */
export function EntryWatch({ id, name, lang, locale, big }: { id: string; name: string; lang?: string; locale: Locale; big?: boolean }) {
  const watching = useWatchlist().some((w) => w.id === id);
  return <WatchButton id={id} name={name} lang={lang} watching={watching} locale={locale} big={big} />;
}
