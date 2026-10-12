import { copy } from "@/lib/lab/o-editorial";
import { getLabLocale as getLocale } from "@/lib/locale";

/* 호를 펴는 동안 — 빈 뼈대를 채우지 않고, 커버 자리를 먼저 깐다(바뀌어도 화면이 튀지 않게). */
export default async function Loading() {
  const c = copy(await getLocale());
  return (
    <section className="oe-cover" aria-busy="true">
      <div className="oe-wrap oe-cover-inner" style={{ minHeight: "min(72vh, 640px)" }}>
        <p role="status" style={{ fontSize: "clamp(28px, 4vw, 56px)", fontWeight: 800, letterSpacing: "-0.035em", lineHeight: 1.1, maxWidth: "14em" }}>{c.loading}</p>
      </div>
    </section>
  );
}
