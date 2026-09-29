import { copy } from "@/lib/lab/o-editorial";
import { getLocale } from "@/lib/locale";

export default async function Loading() {
  const c = copy(await getLocale());
  return (
    <div className="oe-wrap oe-entry-head">
      <p role="status" style={{ marginTop: 24, fontSize: "clamp(28px, 4vw, 48px)", fontWeight: 800, letterSpacing: "-0.035em", lineHeight: 1.1 }}>{c.entryLoading}</p>
    </div>
  );
}
