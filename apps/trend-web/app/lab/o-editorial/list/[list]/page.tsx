import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { IndexItem, LedgerItem, Poster, RubricHead } from "@/components/lab/o-editorial/rubrics";
import { BASE, copy, editionHref, editionName, parseEdition } from "@/lib/lab/o-editorial";
import { getListPage } from "@/lib/lab/o-editorial-data";
import { getLocale } from "@/lib/locale";
import type { KeywordList } from "@/lib/types";

/* 꼭지 전체 — 첫 화면에 다 싣지 못한 목록을 30개씩 쪽으로. 목록과 순서는 백엔드 그대로. */

type Params = { params: Promise<{ list: string }> };
type Props = Params & { searchParams: Promise<Record<string, string | string[] | undefined>> };
const LISTS: KeywordList[] = ["rising", "fading", "caution"];
const first = (v: string | string[] | undefined) => [v].flat()[0];

const title = (c: ReturnType<typeof copy>, l: KeywordList) => (l === "rising" ? c.rubricRising : l === "fading" ? c.rubricFading : c.rubricCaution);
const note = (c: ReturnType<typeof copy>, l: KeywordList) => (l === "rising" ? c.rubricRisingNote : l === "fading" ? c.rubricFadingNote : c.rubricCautionNote);

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const [{ list }, locale] = await Promise.all([params, getLocale()]);
  const c = copy(locale);
  const l = LISTS.find((x) => x === list);
  return { title: l ? `${title(c, l)} | ${c.site}` : c.site };
}

export default async function ListPage({ params, searchParams }: Props) {
  const [{ list }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const l = LISTS.find((x) => x === list);
  if (!l) notFound();
  const c = copy(locale);
  const edition = parseEdition(first(sp.regions));
  const page = Math.max(1, Number.parseInt(first(sp.page) ?? "1", 10) || 1);
  const board = await getListPage(edition, page);
  const q = (p: number) => `${BASE}/list/${l}?regions=${edition === "ALL" ? "all" : edition}${p > 1 ? `&page=${p}` : ""}`;

  if (!board) {
    return (
      <div className="oe-wrap" style={{ paddingBlock: 48 }}>
        <div className="oe-state" role="alert">
          <p>{c.loadFailed}</p>
          <p style={{ marginTop: 16 }}><Link href={q(page)} className="oe-btn oe-btn-line">{c.retry}</Link></p>
        </div>
      </div>
    );
  }
  const total = board.totals[l] ?? 0;
  const last = Math.max(1, Math.ceil(total / (board.page_size || 30)));
  if (page > last) redirect(q(last));
  const items = board[l];
  const at = board.generated_at;

  return (
    <div className="oe-wrap" style={{ paddingTop: 28, paddingBottom: 72 }}>
      <Link href={editionHref(edition)} className="oe-quiet-link" style={{ fontSize: 15, fontWeight: 600 }}>{c.listBack(editionName(locale, edition))}</Link>
      <div style={{ marginTop: 20 }}>
        <RubricHead id={`${l}-title`} title={title(c, l)} count={c.countLine(items.length, total)} note={note(c, l)} />
      </div>
      {l === "rising" && <div className="oe-posters">{items.map((card) => <Poster key={card.term_id} locale={locale} edition={edition} card={card} generatedAt={at} />)}</div>}
      {l === "fading" && <ul className="oe-index">{items.map((card) => <IndexItem key={card.term_id} locale={locale} edition={edition} card={card} generatedAt={at} />)}</ul>}
      {l === "caution" && <ul className="oe-ledger">{items.map((card) => <LedgerItem key={card.term_id} locale={locale} edition={edition} card={card} generatedAt={at} />)}</ul>}
      {last > 1 && (
        <nav className="oe-pager" aria-label={c.pageOf(page, last)}>
          {page > 1 ? <Link href={q(page - 1)} className="oe-btn oe-btn-line oe-btn-small">{c.pagePrev}</Link> : null}
          <span className="oe-meta oe-num" aria-current="page">{c.pageOf(page, last)}</span>
          {page < last ? <Link href={q(page + 1)} className="oe-btn oe-btn-line oe-btn-small">{c.pageNext}</Link> : null}
        </nav>
      )}
    </div>
  );
}
