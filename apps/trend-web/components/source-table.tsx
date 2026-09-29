"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { t, type Locale } from "@/lib/i18n";
import { scriptLang } from "@/lib/lang";
import { fmtDate } from "@/lib/labels";
import type { SourceRow } from "@/lib/sources";

const FIRST = 10;

/* 사전 항목의 출처 표 — 최신이 위, 10건 뒤는 제자리에서 펼친다. 펼치면 새로 보인 첫 줄로 초점을 옮긴다.
   데스크톱은 표(날짜 | 출처 | 내용), 휴대폰은 두 줄 묶음. 제목은 원문 그대로라 글자로 lang 을 짐작한다. */
export function SourceTable({ rows, locale }: { rows: SourceRow[]; locale: Locale }) {
  const [open, setOpen] = useState(false);
  const firstNew = useRef<HTMLElement | null>(null);
  const firstNewMobile = useRef<HTMLElement | null>(null);
  const shown = open ? rows : rows.slice(0, FIRST);
  const rest = rows.length - FIRST;

  useEffect(() => {
    if (!open) return;   // 펼치는 것은 한 번뿐이다 (접지 않는다)
    // 보이는 쪽(표 또는 목록)으로 초점을 옮긴다 — 숨은 쪽은 offsetParent 가 없다
    const target = firstNew.current?.offsetParent ? firstNew.current : firstNewMobile.current;
    target?.focus();
  }, [open]);

  const link = (r: SourceRow) => (
    <a href={r.url} target="_blank" rel="noreferrer noopener" lang={scriptLang(r.title)} className="text-link-blue hover:underline">
      {r.title}<span className="sr-only"> ({t(locale, "term_new_tab")})</span>
    </a>
  );
  const excerpt = (r: SourceRow) => r.excerpt && <p lang={scriptLang(r.excerpt)} className="mt-1 text-[13px] leading-[1.5] text-steel">“{r.excerpt}”</p>;

  return (
    <div className="space-y-4">
      <table className="hidden w-full border-collapse text-left text-[14px] md:table">
        <thead>
          <tr className="border-b border-hairline text-[13px] text-steel">
            <th scope="col" className="w-[104px] py-2 pr-4 font-medium">{t(locale, "term_col_date")}</th>
            <th scope="col" className="w-[180px] py-2 pr-4 font-medium">{t(locale, "term_col_source")}</th>
            <th scope="col" className="py-2 font-medium">{t(locale, "term_col_content")}</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={r.id} ref={i === FIRST ? (el) => { firstNew.current = el; } : undefined} tabIndex={i === FIRST ? -1 : undefined}
              className="border-b border-hairline align-top outline-none focus-visible:bg-surface-soft">
              <td className="py-2.5 pr-4 tabular-nums text-charcoal">{fmtDate(r.date)}</td>
              <td className="py-2.5 pr-4 text-charcoal">{r.source}</td>
              <td className="py-2.5">{link(r)}{excerpt(r)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="divide-y divide-hairline border-y border-hairline md:hidden">
        {shown.map((r, i) => (
          <li key={r.id} ref={i === FIRST ? (el) => { firstNewMobile.current = el; } : undefined} tabIndex={i === FIRST ? -1 : undefined}
            className="py-3 text-[14px] outline-none">
            <div className="flex items-baseline justify-between gap-3 text-[13px] text-steel">
              <span>{r.source}</span>
              <span className="shrink-0 tabular-nums">{fmtDate(r.date)}</span>
            </div>
            <div className="mt-1 break-words">{link(r)}</div>
            {excerpt(r)}
          </li>
        ))}
      </ul>

      {!open && rest > 0 && (
        <Button type="button" variant="outline" className="h-10 w-full rounded-md border-hairline-strong px-4 text-[14px] shadow-none sm:w-auto"
          onClick={() => setOpen(true)}>
          {t(locale, "term_show_more").replace("{n}", String(rest))}
        </Button>
      )}
    </div>
  );
}
