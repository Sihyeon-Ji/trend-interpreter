import { TermView } from "@/components/lab/r-flow/term-view";
import { isMarket } from "@/components/lab/r-flow/copy";
import { getLabLocale as getLocale } from "@/lib/locale";

type Props = { params: Promise<{ termId: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function PanelTerm({ params, searchParams }: Props) {
  const [{ termId }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const m = [sp.m].flat()[0];
  return <TermView termId={decodeURIComponent(termId)} locale={locale} mode="panel" regions={isMarket(m) ? [m] : []} />;
}
