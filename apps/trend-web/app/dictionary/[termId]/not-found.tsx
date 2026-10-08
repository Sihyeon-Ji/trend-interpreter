import Link from "next/link";
import { tx } from "@/components/stage/copy";
import { getLocale } from "@/lib/locale";

export default async function NotFound() {
  const locale = await getLocale();
  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <section className="rs-stage rs-stage-empty" aria-labelledby="rs-nf-h">
        <h1 id="rs-nf-h" className="rs-lede">{tx(locale, "tm_not_found")}</h1>
        <p className="rs-quiet">{tx(locale, "tm_not_found_note")}</p>
        <Link href="/trends" className="rs-btn" data-kind="primary">{tx(locale, "nav_explore")}</Link>
      </section>
    </main>
  );
}
