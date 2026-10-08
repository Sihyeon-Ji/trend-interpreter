import type { Metadata } from "next";
import { TermView } from "@/components/lab/r-flow/term-view";
import { isMarket } from "@/components/lab/r-flow/copy";
import { getTermRecord } from "@/lib/data";
import { getLocale } from "@/lib/locale";

/* 밈 하나 — 전체 화면. 같은 주소를 화면 안에서 열면 옆 패널(@panel/(.)term)로 열린다. */
type Props = { params: Promise<{ termId: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ params }: Pick<Props, "params">): Promise<Metadata> {
  const { termId } = await params;
  const record = await getTermRecord(decodeURIComponent(termId)).catch(() => null);
  return { title: record ? record.term.canonical : "Meme" };
}

export default async function TermPage({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const m = [sp.m].flat()[0];
  return <TermView termId={decodeURIComponent(termId)} locale={locale} mode="page" regions={isMarket(m) ? [m] : []} />;
}
