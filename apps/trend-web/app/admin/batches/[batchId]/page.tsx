import Link from "next/link";
import { notFound } from "next/navigation";
import { getPublicationBatch } from "@/lib/data";
import { getLocale } from "@/lib/locale";
import { t, type Locale } from "@/lib/i18n";
import type { MeaningText } from "@/lib/types";
import { fmtDateTime } from "@/lib/labels";
import { BatchDecision } from "@/components/batch-decision";

function JsonData({ value }: { value: unknown }) {
  return <pre className="whitespace-pre-wrap break-all text-xs leading-6">{JSON.stringify(value, null, 2)}</pre>;
}

function MeaningData({ meaning, locale }: { meaning: MeaningText | null; locale: Locale }) {
  if (!meaning) return <p className="text-sm text-steel">{t(locale, "batch_none")}</p>;
  return <dl className="space-y-3 text-sm">
    {([ ["batch_definition", meaning.definition], ["batch_origin", meaning.origin], ["batch_nuance", meaning.nuance] ] as const).map(([key, text]) =>
      <div key={key}><dt className="font-medium text-steel">{t(locale, key)}</dt><dd className="whitespace-pre-wrap break-words">{text}</dd></div>)}
  </dl>;
}

function Translations({ translations, locale }: { translations: Record<string, MeaningText>; locale: Locale }) {
  return <div className="space-y-3"><h5 className="text-sm font-medium">{t(locale, "batch_translations")}</h5>
    {Object.keys(translations).length === 0 ? <p className="text-sm text-steel">{t(locale, "batch_none")}</p> :
      Object.entries(translations).map(([lang, meaning]) => <div key={lang}><p className="text-xs text-steel">{lang}</p><MeaningData meaning={meaning} locale={locale} /></div>)}
  </div>;
}

export default async function BatchPage({ params }: { params: Promise<{ batchId: string }> }) {
  const [locale, { batchId }] = await Promise.all([getLocale(), params]);
  const result = await getPublicationBatch(batchId);
  if (!result) notFound();
  const { batch, current, validation } = result;
  const changed = result.status !== "published" && Object.values(current).some((item) => item.baseline_changed);
  const warnings = Object.values(validation).some((items) => items.length > 0);
  return <section className="space-y-6">
    <Link href="/admin/batches" className="text-sm text-link-blue hover:underline">{t(locale, "batch_back")}</Link>
    <h2 className="break-all text-lg font-semibold">{batch.batch_id}</h2>
    <p>{t(locale, `batch_${result.status}`)}</p>
    <p className="text-sm text-charcoal">{t(locale, "batch_intro")}</p>
    {result.reviewed_by && <p className="text-sm">{t(locale, "batch_decided")}: {result.reviewed_by} · {result.reviewed_at ? fmtDateTime(result.reviewed_at, locale) : "∅"}</p>}
    {result.failure_code && <p role="status" className="text-sm">{result.failure_code}</p>}
    {changed && <p role="alert">{t(locale, "batch_changed")}</p>}
    <details className="border-y border-hairline py-3">
      <summary className="cursor-pointer text-sm">{t(locale, "batch_versions")}</summary>
      <JsonData value={{ snapshot_id: batch.snapshot_id, snapshot_sha256: batch.snapshot_sha256,
        model_id: batch.model_id, prompt_version: batch.prompt_version, rule_version: batch.rule_version,
        payload_sha256: result.payload_sha256 }} />
    </details>
    {batch.items.map((item) => <article key={item.term_id} className="space-y-4 border-b border-hairline pb-6">
      <h3 className="break-all font-semibold">{current[item.term_id].term?.canonical ?? item.new_term?.canonical ?? item.term_id}</h3>
      <p className="break-all text-xs text-steel">{item.term_id} · {item.expected_meaning_id ?? "∅"}</p>
      {validation[item.term_id]?.length > 0 && <div><h4 className="text-sm font-medium">{t(locale, "batch_warnings")}</h4><JsonData value={validation[item.term_id]} /></div>}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="min-w-0 space-y-4"><h4 className="text-sm font-medium">{t(locale, "batch_before")}</h4>
          <MeaningData meaning={current[item.term_id].meaning} locale={locale} />
          <Translations translations={current[item.term_id].translations} locale={locale} />
          <details><summary className="cursor-pointer text-sm">{t(locale, "batch_more")}</summary><JsonData value={current[item.term_id]} /></details>
        </div>
        <div className="min-w-0 space-y-4"><h4 className="text-sm font-medium">{t(locale, "batch_after")}</h4>
          {item.meaning ? <MeaningData meaning={item.meaning} locale={locale} /> : <p className="text-sm text-steel">{t(locale, "batch_unchanged")}</p>}
          {Object.keys(item.translations).length > 0 && <Translations translations={item.translations} locale={locale} />}
          {Object.keys(item.country_notes).length > 0 && <div><h5 className="text-sm font-medium">{t(locale, "batch_notes")}</h5><JsonData value={item.country_notes} /></div>}
          {item.fit != null && <div><h5 className="text-sm font-medium">{t(locale, "batch_fit")}</h5><JsonData value={item.fit} /></div>}
          <details><summary className="cursor-pointer text-sm">{t(locale, "batch_more")}</summary><JsonData value={item} /></details>
        </div>
      </div>
      <details><summary className="cursor-pointer text-sm">{t(locale, "batch_sources")}</summary>
        <ul className="space-y-3 py-3">{[...current[item.term_id].evidences, ...item.evidences].map((evidence, index) =>
          <li key={`${evidence.evidence_id}-${index}`} className="space-y-1 text-sm">
            {/^https?:\/\//.test(evidence.url) ? <a href={evidence.url} target="_blank" rel="noopener noreferrer" className="break-all text-link-blue hover:underline">{evidence.title || evidence.url}</a> : <span>{evidence.title}</span>}
            <p className="whitespace-pre-wrap break-words">{evidence.excerpt}</p>
          </li>)}</ul><JsonData value={{ citations: item.citations }} />
      </details>
    </article>)}
    {result.status === "draft" && <BatchDecision batchId={batch.batch_id} checksum={result.payload_sha256} warnings={warnings} changed={changed} locale={locale} />}
  </section>;
}
