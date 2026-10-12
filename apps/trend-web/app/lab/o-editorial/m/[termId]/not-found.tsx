import Link from "next/link";
import { BASE, copy, editionName } from "@/lib/lab/o-editorial";
import { getLabLocale as getLocale } from "@/lib/locale";

export default async function EntryNotFound() {
  const locale = await getLocale();
  const c = copy(locale);
  return (
    <div className="oe-wrap" style={{ paddingBlock: 48 }}>
      <div className="oe-state">
        <h1 style={{ fontSize: 28, fontWeight: 800, lineHeight: 1.25 }}>{c.notFoundTitle}</h1>
        <p style={{ marginTop: 10 }}>{c.notFoundBody}</p>
        <form action={`${BASE}/search`} method="get" role="search" className="oe-search-form">
          <label htmlFor="oe-q-nf" className="oe-sr">{c.searchLabel}</label>
          <input id="oe-q-nf" name="q" type="search" placeholder={c.searchPlaceholder} autoComplete="off" />
          <button type="submit">{c.searchButton}</button>
        </form>
        <p style={{ marginTop: 20 }}><Link href={BASE} className="oe-link">{c.backTo(editionName(locale, "KR"))}</Link></p>
      </div>
    </div>
  );
}
