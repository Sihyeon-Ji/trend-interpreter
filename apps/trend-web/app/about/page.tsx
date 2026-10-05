import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { t, type StringKey } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

/* 이 서비스는 어떻게 만들어지나요 — 이용자 말로 쓴 만드는 순서와 AI·사람·규칙의 몫. 모델 이름은 '누가 무엇을 하나' 정도로만 쓰고,
   단계별 건수·모델 버전·시각 같은 운영 기록은 관리 화면(/admin/status)에 둔다(이용자 화면에 내부 용어를 내지 않는다). */
const STEPS = ["collect", "draft", "check", "judge", "use"] as const;
const RULES = ["about_rule_1", "about_rule_2", "about_rule_3", "about_rule_4"] as const;

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "about_title")} — ${t(locale, "site")}` };
}

export default async function AboutPage() {
  const locale = await getLocale();
  return (
    <PageShell>
      <div className="max-w-[760px] space-y-10">
        <PageHeader title={t(locale, "about_title")} description={t(locale, "about_intro")} />

        <section className="space-y-4">
          <h2 className="text-[18px] font-semibold text-ink">{t(locale, "about_steps_title")}</h2>
          <ol className="space-y-4">
            {STEPS.map((id, i) => (
              <li key={id} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
                <span className="grid h-7 w-7 place-items-center rounded-full border border-hairline text-[13px] tabular-nums text-charcoal">{i + 1}</span>
                <div className="space-y-1">
                  <p className="text-[15px] font-semibold text-ink">{t(locale, `about_step_${id}` as StringKey)}</p>
                  <p className="text-[14px] leading-[1.65] text-charcoal">{t(locale, `about_step_${id}_body` as StringKey)}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="space-y-3">
          <h2 className="text-[18px] font-semibold text-ink">{t(locale, "about_rules_title")}</h2>
          <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-[1.65] text-charcoal">
            {RULES.map((k) => <li key={k}>{t(locale, k)}</li>)}
          </ul>
        </section>

        <p className="text-[14px] text-charcoal">
          {t(locale, "about_see_entry")} <Link href="/dictionary" className="text-link-blue hover:underline">{t(locale, "nav_dictionary")} →</Link>
        </p>
      </div>
    </PageShell>
  );
}
