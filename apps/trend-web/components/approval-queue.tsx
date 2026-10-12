"use client";

import { ChevronRight, ListChecks, Sparkles, Stamp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ActorTag } from "@/components/stage/bits";
import { marketName, tx, type CopyKey } from "@/components/stage/copy";
import { isBlocking } from "@/lib/approval";
import { t, type Locale, type StringKey } from "@/lib/i18n";
import { fmtDateTime, sep } from "@/lib/labels";
import { langTag, scriptLang } from "@/lib/lang";
import type { ApprovalGroup, ApprovalItem, ApprovalList } from "@/lib/types";

/* 관리 '문구 승인'(Plan 20 ⑤) — 초안 화면에서 온 검수 요청과 지난 기록. AI 점수로 줄 세우지 않는다: 묶음은 서버가 규칙 검사 결과로
   정한 그대로(막힘·읽어 볼 것·깨끗함), 묶음 안은 최신순. 처음 열면 '읽어 볼 것' 이 펼쳐진다.
   막힌 요청은 승인 단추를 끄고 까닭을 보인다. 읽기 전용 계정은 보기만 한다(단추가 꺼지고, 서버도 403).
   승인하면 서버가 지금 사전으로 규칙 검사를 다시 하고, 그사이 막힌 말이 됐으면 승인하지 않고 막힘으로 옮긴다. */

const GROUPS: ApprovalGroup[] = ["blocked", "read", "clean"];
const GROUP_KEY = { blocked: "apq_g_blocked", read: "apq_g_read", clean: "apq_g_clean" } as const;
const FIT_KEY = { ok: "apq_ai_ok", off: "apq_ai_off", unsure: "apq_ai_unsure" } as const;
const fill = (s: string, v: Record<string, string | number>) => Object.entries(v).reduce((acc, [k, x]) => acc.replaceAll(`{${k}}`, String(x)), s);
const why = (locale: Locale, code: string) => t(locale, `apq_why_${code}` as StringKey);

type Change = Partial<Pick<ApprovalItem, "status" | "group" | "reasons" | "decided_by" | "decided_at" | "memo">>;

export function ApprovalQueue({ list, locale, live, readOnly }: { list: ApprovalList; locale: Locale; live: boolean; readOnly: boolean }) {
  const router = useRouter();
  const [changed, setChanged] = useState<Record<string, Change>>({});
  const [memo, setMemo] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, StringKey>>({});
  const [open, setOpen] = useState<Record<ApprovalGroup, boolean>>({ blocked: false, read: true, clean: false });

  const items = list.pending.map((p) => ({ ...p, ...changed[p.approval_id] }));
  const pending = items.filter((p) => p.status === "pending");
  const history = [...items.filter((p) => p.status !== "pending").sort((a, b) => (b.decided_at ?? "").localeCompare(a.decided_at ?? "")), ...list.history];

  async function decide(it: ApprovalItem, decision: "approve" | "reject") {
    const id = it.approval_id;
    setBusy((b) => ({ ...b, [id]: true }));
    setErrors((e) => { const n = { ...e }; delete n[id]; return n; });
    try {
      const res = await fetch(`/api/approvals/${encodeURIComponent(id)}`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ decision, memo: memo[id] ?? "" }),
      });
      const json = (await res.json().catch(() => ({}))) as Change & { error?: string; reasons?: string[] };
      if (res.ok) {
        setChanged((c) => ({ ...c, [id]: { status: json.status, decided_by: json.decided_by, decided_at: json.decided_at, memo: json.memo ?? null } }));
        if (live) router.refresh();          // 지난 기록과 다른 검수자의 결정을 다시 읽는다(관리 조회는 캐시하지 않는다)
        return;
      }
      if (res.status === 409 && json.error === "blocked") {
        setChanged((c) => ({ ...c, [id]: { group: "blocked", reasons: json.reasons ?? it.reasons } }));
        setOpen((o) => ({ ...o, blocked: true }));
      }
      setErrors((e) => ({ ...e, [id]: res.status === 409 ? (json.error === "blocked" ? "apq_err_blocked" : json.error === "expired" ? "apq_err_expired" : "apq_err_decided")
        : res.status === 403 ? "apq_err_403" : "apq_err_other" }));
      if (live && res.status === 409) router.refresh();
    } catch {
      setErrors((e) => ({ ...e, [id]: "apq_err_other" }));
    } finally {
      setBusy((b) => ({ ...b, [id]: false }));
    }
  }

  return (
    <div className="space-y-8">
      <section aria-labelledby="apq-queue-h" className="space-y-3">
        <h3 id="apq-queue-h" className="text-[17px] font-semibold text-ink">
          {t(locale, "apq_queue")} <span className="ml-1 text-[14px] font-normal tabular-nums text-steel">{pending.length}</span>
        </h3>
        {pending.length === 0 && <p className="text-[14px] text-charcoal">{t(locale, "apq_empty")}</p>}
        <div className="divide-y divide-hairline border-y border-hairline" role="group" aria-label={t(locale, "apq_groups_label")}>
          {GROUPS.map((g) => {
            const rows = pending.filter((p) => p.group === g);
            return (
              <details key={g} open={open[g]} data-group={g} className="group"
                onToggle={(e) => { const v = e.currentTarget.open; setOpen((o) => (o[g] === v ? o : { ...o, [g]: v })); }}>
                <summary className="flex cursor-pointer list-none items-baseline gap-2 py-3 text-[15px] font-semibold text-ink [&::-webkit-details-marker]:hidden">
                  <ChevronRight aria-hidden="true" size={16} className="shrink-0 self-center text-steel transition-transform group-open:rotate-90" />
                  <span className={g === "blocked" && rows.length ? "text-avoid" : undefined}>{t(locale, GROUP_KEY[g])}</span>
                  <span className="text-[14px] font-normal tabular-nums text-steel">{rows.length}</span>
                </summary>
                <p className="pb-3 text-[13px] leading-[1.55] text-charcoal">{t(locale, `${GROUP_KEY[g]}_note` as StringKey)}</p>
                {rows.length ? (
                  <ul className="divide-y divide-hairline border-t border-hairline">
                    {rows.map((it) => (
                      <Request key={it.approval_id} it={it} locale={locale} readOnly={readOnly} busy={!!busy[it.approval_id]} error={errors[it.approval_id]}
                        memo={memo[it.approval_id] ?? ""} onMemo={(v) => setMemo((m) => ({ ...m, [it.approval_id]: v }))} onDecide={(d) => void decide(it, d)} />
                    ))}
                  </ul>
                ) : <p className="pb-4 text-[14px] text-steel">{t(locale, "apq_g_empty")}</p>}
              </details>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="apq-history-h" className="space-y-3">
        <h3 id="apq-history-h" className="text-[17px] font-semibold text-ink">{t(locale, "apq_history")}</h3>
        {history.length ? (
          <ul className="divide-y divide-hairline border-y border-hairline">
            {history.map((it) => <Past key={it.approval_id} it={it} locale={locale} />)}
          </ul>
        ) : <p className="text-[14px] text-charcoal">{t(locale, "apq_history_empty")}</p>}
      </section>
    </div>
  );
}

/** 문구 목록 — 문구마다 규칙 검사 결과, AI 의견은 받은 한 문구에만 */
function Copies({ it, locale }: { it: ApprovalItem; locale: Locale }) {
  const lang = langTag(it.market === "JP" ? "ja" : it.market === "GLOBAL" ? "en" : "ko");
  const nums = it.copies.map((c, i) => it.copies.slice(0, i + 1).filter((d) => d.platform === c.platform).length);
  return (
    <ol className="space-y-3">
      {it.copies.map((c, i) => (
        <li key={i} className="space-y-1.5">
          <p className="text-[12.5px] font-semibold text-steel">{c.platform === "x" ? "X" : "Instagram"} {nums[i]}</p>
          {c.text != null && <p className="text-[15px] leading-[1.6] text-ink" lang={lang}>{c.text}</p>}
          {c.hashtags.length > 0 && <p className="flex flex-wrap gap-x-2 text-[13px] text-steel" lang={lang}>{c.hashtags.map((h) => <span key={h}>#{h}</span>)}</p>}
          <div className="rs-copy-checks">
            <span className="rs-check" data-state={c.issues.length ? "flag" : "ok"} data-avoid={c.issues.some(isBlocking)}>
              <ListChecks aria-hidden="true" size={14} />
              <span className="rs-sr">{tx(locale, "cp_rule")}: </span>
              {c.issues.length ? [...new Set(c.issues.map((x) => tx(locale, `cp_issue_${x}` as CopyKey)))].join(sep(locale)) : t(locale, "apq_rule_ok")}
            </span>
            {i === it.fit_copy && it.fit ? (
              <span className="rs-check" data-who="ai" data-state={it.fit === "ok" ? "ok" : "flag"}>
                <Sparkles aria-hidden="true" size={14} />
                <span className="rs-sr">{t(locale, "apq_ai")}: </span>
                {t(locale, FIT_KEY[it.fit])}
              </span>
            ) : null}
          </div>
          {i === it.fit_copy && it.fit_note && <p className="text-[13px] leading-[1.55] text-charcoal" lang={scriptLang(it.fit_note)}>{it.fit_note}</p>}
        </li>
      ))}
    </ol>
  );
}

function Request({ it, locale, readOnly, busy, error, memo, onMemo, onDecide }: {
  it: ApprovalItem; locale: Locale; readOnly: boolean; busy: boolean; error?: StringKey; memo: string; onMemo: (v: string) => void; onDecide: (d: "approve" | "reject") => void;
}) {
  const id = it.approval_id;
  const market = marketName(locale, it.market);
  const rules = it.reasons.filter((r) => !r.startsWith("fit_"));
  const ai = it.reasons.find((r) => r.startsWith("fit_"));
  // 승인을 끄는 까닭 — 읽기 전용 계정이 먼저, 다음은 본문 없음·막힘
  const noApprove: StringKey | null = readOnly ? "apq_readonly_why" : it.expired ? "apq_expired_why" : it.group === "blocked" ? "apq_blocked_why" : null;
  const aria = (action: string) => fill(t(locale, "apq_action_aria"), { market, meme: it.canonical, action });
  return (
    <li className="space-y-4 py-5" aria-labelledby={`apq-${id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p id={`apq-${id}`} className="flex flex-wrap items-baseline gap-x-3">
          <span className="text-[13px] text-steel">{market}</span>
          <Link href={`/dictionary/${encodeURIComponent(it.term_id)}?m=${it.market}`} lang={langTag(it.lang)} className="text-[18px] font-semibold text-ink hover:underline">{it.canonical}</Link>
        </p>
        <span className="text-[13px] tabular-nums text-steel">{fill(t(locale, "apq_requested"), { who: it.requested_by, date: fmtDateTime(it.requested_at, locale) })}</span>
      </div>
      <p className="text-[14px] text-charcoal">
        <span className="mr-2 text-steel">{t(locale, "apq_product")}</span>{it.expired ? t(locale, "apq_expired") : it.product}
      </p>
      {(rules.length > 0 || ai) && (
        <div className="space-y-1.5">
          <p className="text-[13px] font-medium text-steel">{t(locale, "apq_reasons")}</p>
          <ul className="space-y-1">
            {rules.map((r) => (
              <li key={r} className={isBlocking(r) ? "text-avoid" : undefined}><ActorTag who="rule" locale={locale}>{why(locale, r)}</ActorTag></li>
            ))}
            {ai && <li><ActorTag who="ai" locale={locale}>{why(locale, ai)}</ActorTag></li>}
          </ul>
        </div>
      )}
      {!it.expired && <Copies it={it} locale={locale} />}
      {it.image_meme && <p className="text-[13px] text-charcoal"><ActorTag who="rule" locale={locale}>{t(locale, "apq_rights")}</ActorTag></p>}
      <div className="space-y-2">
        <label htmlFor={`apq-memo-${id}`} className="block text-[13px] font-medium text-steel">{t(locale, "apq_memo")}</label>
        <textarea id={`apq-memo-${id}`} value={memo} onChange={(e) => onMemo(e.target.value)} maxLength={500} rows={2} disabled={readOnly || busy}
          className="w-full max-w-[560px] rounded-md border border-hairline-strong bg-background px-3 py-2 text-[14px] text-ink disabled:opacity-60" />
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="rs-btn" data-kind="primary" data-size="s" disabled={!!noApprove || busy} aria-label={aria(t(locale, "apq_approve"))}
            aria-describedby={noApprove ? `apq-why-${id}` : undefined} onClick={() => onDecide("approve")}>
            <Stamp aria-hidden="true" size={15} />{t(locale, "apq_approve")}
          </button>
          <button type="button" className="rs-btn" data-kind="quiet" data-size="s" disabled={readOnly || busy} aria-label={aria(t(locale, "apq_reject"))}
            aria-describedby={readOnly ? `apq-why-${id}` : undefined} onClick={() => onDecide("reject")}>
            {t(locale, "apq_reject")}
          </button>
          {busy && <span className="text-[13px] text-steel" role="status">{t(locale, "apq_saving")}</span>}
        </div>
        {noApprove && <p id={`apq-why-${id}`} className={it.group === "blocked" && !readOnly ? "text-[13px] text-avoid" : "text-[13px] text-steel"}>{t(locale, noApprove)}</p>}
        {error && <p role="alert" className="text-[13px] text-avoid">{t(locale, error)}</p>}
      </div>
    </li>
  );
}

function Past({ it, locale }: { it: ApprovalItem; locale: Locale }) {
  const done = fill(t(locale, it.status === "approved" ? "apq_done_approved" : "apq_done_rejected"), { who: it.decided_by ?? "", date: fmtDateTime(it.decided_at, locale) });
  return (
    <li className="space-y-2 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p className="flex flex-wrap items-baseline gap-x-3">
          <span className="text-[13px] text-steel">{marketName(locale, it.market)}</span>
          <span lang={langTag(it.lang)} className="text-[16px] font-semibold text-ink">{it.canonical}</span>
        </p>
        <ActorTag who="human" locale={locale}>{done}</ActorTag>
      </div>
      <p className="text-[13px] text-charcoal">
        <span className="mr-2 text-steel">{t(locale, "apq_product")}</span>{it.expired ? t(locale, "apq_expired") : it.product}
        <span className="ml-3 tabular-nums text-steel">{fill(t(locale, "apq_requested"), { who: it.requested_by, date: fmtDateTime(it.requested_at, locale) })}</span>
      </p>
      {it.memo && <p className="text-[13px] text-ink"><span className="mr-2 text-steel">{tx(locale, "ap_memo")}</span>{it.memo}</p>}
      {!it.expired && (
        <details className="text-[13px]">
          <summary className="cursor-pointer text-link-blue">{t(locale, "apq_copies")} {it.copies.length}</summary>
          <div className="pt-3"><Copies it={it} locale={locale} /></div>
        </details>
      )}
    </li>
  );
}
