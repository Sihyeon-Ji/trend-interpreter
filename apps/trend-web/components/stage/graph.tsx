/* 이어진 밈 — 지식 그래프의 한 다리. 가운데 말에서 오른쪽으로 가지가 뻗고, 가지마다 관계(변형·비슷한 밈·여기서 나옴…)를 단다.
   사전에 있는 말은 그 항목으로 가는 링크, 아직 없는 말은 흐리게. 나온 곳(작품·인물·사건)은 같은 곳에서 나온 다른 밈을 묶는다.
   커뮤니티가 나온 곳이면 사이트 이름을 내지 않는다(ADR 0003). 훅이 없어 서버·클라이언트 어디서나 쓴다. */
import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import type { TermRelated } from "@/lib/types";
import { DOMAIN_EN, KIND_EN, tx, type CopyKey } from "./copy";

const REL: Record<string, CopyKey> = {
  derived_from: "rel_derived_from", derived_into: "rel_derived_into", variant: "rel_variant", opposite: "rel_opposite",
  similar: "rel_similar", parody_of: "rel_parody_of", linked: "rel_linked",
};
const relLabel = (locale: Locale, rel: string) => tx(locale, REL[rel.toLowerCase()] ?? "rel_linked");
const SRC: Record<string, CopyKey> = { work: "src_work", person: "src_person", event: "src_event", ad: "src_ad", platform: "src_platform", community: "src_community", unknown: "src_unknown" };

export function hasGraph(g: TermRelated | null): boolean {
  return !!g && (g.related.length > 0 || g.candidates.length > 0 || g.same_source.length > 0 || !!g.card);
}

type Branch =
  | { kind: "term"; key: string; rel: string; id: string; name: string; lang: string }
  | { kind: "cand"; key: string; rel: string; name: string }
  | { kind: "src"; key: string; type: string; name: string; same: { term_id: string; canonical: string; lang: string }[] };

export function RelGraph({ word, lang, graph, href, locale, play = true }: {
  word: string; lang?: string | null; graph: TermRelated; href: (termId: string) => string; locale: Locale; play?: boolean;
}) {
  const card = graph.card;
  const kind = card ? (locale === "ko" ? card.kind_ko : KIND_EN[card.kind] ?? card.kind) : null;
  const domains = card ? (locale === "ko" ? card.domains_ko : card.domains.map((d) => DOMAIN_EN[d] ?? d.replace(/_/g, " "))) : [];
  const source = graph.source ?? (card && card.source_type !== "unknown" ? { type: card.source_type, name: card.source_name } : null);
  const branches: Branch[] = [
    ...graph.related.map((r): Branch => ({ kind: "term", key: `r-${r.term_id}`, rel: r.rel, id: r.term_id, name: r.canonical, lang: r.lang })),
    ...graph.candidates.slice(0, 4).map((c): Branch => ({ kind: "cand", key: `c-${c.name}`, rel: c.rel, name: c.name })),
  ];
  const srcName = source && source.type !== "community" ? source.name : "";
  if (source && (srcName || graph.same_source.length)) branches.push({ kind: "src", key: "src", type: source.type, name: srcName, same: graph.same_source.slice(0, 4) });

  return (
    <div className="rs-graph" data-play={play}>
      {kind || domains.length ? (
        <dl className="rs-g-card">
          {kind ? <div><dt>{tx(locale, "tm_kind")}</dt><dd>{kind}</dd></div> : null}
          {domains.length ? <div><dt>{tx(locale, "tm_domains")}</dt><dd>{domains.join(", ")}</dd></div> : null}
        </dl>
      ) : null}
      {branches.length ? (
        <div className="rs-g-tree">
          <span className="rs-g-root" lang={langTag(lang)}>{word}</span>
          <ul className="rs-g-branches">
            {branches.map((b, i) => (
              <li key={b.key} style={{ "--i": i } as React.CSSProperties} data-out={b.kind === "cand" || undefined}>
                {b.kind === "term" ? (
                  <>
                    <span className="rs-g-rel">{relLabel(locale, b.rel)}</span>
                    <Link className="rs-g-node" href={href(b.id)} lang={langTag(b.lang)}>{b.name}</Link>
                  </>
                ) : b.kind === "cand" ? (
                  <>
                    <span className="rs-g-rel">{relLabel(locale, b.rel)}</span>
                    <span className="rs-g-node" lang={scriptLang(b.name)}>{b.name}</span>
                    <span className="rs-g-note">{tx(locale, "tm_not_in_dict")}</span>
                  </>
                ) : (
                  <>
                    <span className="rs-g-rel">{tx(locale, "tm_source")}</span>
                    <span className="rs-g-node" data-kind="source">
                      {b.name ? <span lang={scriptLang(b.name)}>{b.name}</span> : null}
                      <span className="rs-g-type">{tx(locale, SRC[b.type] ?? "src_unknown")}</span>
                    </span>
                    {b.same.length ? (
                      <span className="rs-g-same">
                        {b.same.map((s) => <Link key={s.term_id} href={href(s.term_id)} lang={langTag(s.lang)} className="rs-link">{s.canonical}</Link>)}
                      </span>
                    ) : null}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="rs-quiet">{tx(locale, "tm_linked_none")}</p>
      )}
    </div>
  );
}
