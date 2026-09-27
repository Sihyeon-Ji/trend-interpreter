import { t, type Locale } from "@/lib/i18n";
import { L, fmtDate, joinGens, joinRegions } from "@/lib/labels";
import type { Meaning } from "@/lib/types";

/* 변경 기록: 최신이 위. 지운 기록은 없다. 기록 본문은 원문(한국어). */
export function ChangeHistory({ meanings, locale }: { meanings: Meaning[]; locale: Locale }) {
  const ordered = [...meanings].sort((a, b) => b.version - a.version);
  const field = locale === "ko"
    ? { definition: "뜻", nuance: "뉘앙스", origin: "유래", generations: "주 사용 세대", regions: "쓰이는 곳", other: "내용" }
    : { definition: "meaning", nuance: "nuance", origin: "origin", generations: "age groups", regions: "regions", other: "content" };
  return (
    <ol className="divide-y divide-hairline-soft">
      {ordered.map((m, i) => {
        const prev = ordered[i + 1];
        const changed: string[] = [];
        if (prev) {
          if (prev.definition !== m.definition) changed.push(field.definition);
          if (prev.nuance !== m.nuance) changed.push(field.nuance);
          if (prev.origin !== m.origin) changed.push(field.origin);
          if (prev.generations.join() !== m.generations.join()) changed.push(field.generations);
          if (prev.regions.join() !== m.regions.join()) changed.push(field.regions);
        }
        const first = i === ordered.length - 1;
        const what = first ? t(locale, "history_first") : `${changed.length ? changed.join(locale === "ko" ? "·" : ", ") : field.other} ${t(locale, "history_updated")}`;
        return (
          <li key={m.meaning_id} className="grid gap-1 py-3 text-[14px] sm:grid-cols-[180px_1fr]">
            <div className="text-steel tabular-nums">{fmtDate(m.valid_from)} – {m.valid_to ? fmtDate(m.valid_to) : t(locale, "history_now")}</div>
            <div>
              <div className="text-ink">{what}<span className="text-steel"> · {L(locale).verification[m.verification ?? "unverified"]}</span></div>
              {!first && changed.includes(field.nuance) && <p className="mt-1 text-charcoal">{m.nuance}</p>}
              {first && <p className="mt-1 text-charcoal">{m.definition} ({joinGens(locale, m.generations)} · {joinRegions(locale, m.regions)})</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
