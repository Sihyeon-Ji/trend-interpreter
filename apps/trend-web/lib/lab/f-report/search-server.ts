import "server-only";
import { loadTermRecords } from "@/lib/data";
import { textFor } from "@/lib/explain";
import type { Locale } from "@/lib/i18n";
import type { SearchHit } from "./search";

export async function loadSearchIndex(locale: Locale): Promise<SearchHit[] | null> {
  const { records, ok } = await loadTermRecords();
  if (!ok) return null;
  return records
    .filter((r) => r.term.status === "verified")
    .map((r) => ({
      id: r.term.term_id,
      name: r.term.canonical,
      lang: r.term.lang ?? "",
      aliases: (r.term.aliases ?? []).filter((a) => a && a !== r.term.canonical).slice(0, 4),
      gloss: (textFor(r, locale)?.definition ?? "").slice(0, 80),
      risk: r.term.risk_level ?? null,
    }));
}
