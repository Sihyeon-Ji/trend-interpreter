"use client";

/* 제목 속 지역 — 누르면 여러 곳을 고르는 창이 열린다(fixed inset-0 + flex 가운데, 변형 없이). 고른 지역은 주소에만 둔다(?regions=KR,JP). */
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { LabLocale as Locale } from "@/lib/i18n";
import { tr } from "@/lib/lab/o-report/copy";

export interface RegionOption { code: string; label: string; count: number }

export function RegionPicker({ locale, label, options, picked, keep }: {
  locale: Locale; label: string; options: RegionOption[]; picked: string[]; keep: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<string[]>(picked);
  const [warn, setWarn] = useState(false);
  const [host, setHost] = useState<Element | null>(null);   // 창을 붙일 곳 — 초안 틀 안(토큰이 닿게), 제목 밖
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const hintId = useId();

  const targets = options.filter((o) => o.code !== "GLOBAL").map((o) => o.code);

  const show = () => { setHost(trigger.current?.closest(".lab-o-report") ?? document.body); setSel(picked); setWarn(false); setOpen(true); };
  const close = () => { setOpen(false); trigger.current?.focus(); };

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLInputElement>("input")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); setOpen(false); trigger.current?.focus(); }
      if (e.key === "Tab" && panel.current) {          // 창 안에서만 돈다
        const f = [...panel.current.querySelectorAll<HTMLElement>("input,button")].filter((x) => !x.hasAttribute("disabled"));
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prev; document.removeEventListener("keydown", onKey); };
  }, [open]);

  const toggle = (code: string) => setSel((s) => (s.includes(code) ? s.filter((x) => x !== code) : [...s, code]));

  const apply = () => {
    if (!sel.length) { setWarn(true); return; }
    const order = options.map((o) => o.code).filter((c) => sel.includes(c));
    const all = order.length === targets.length && targets.every((c) => order.includes(c));
    const q = new URLSearchParams(keep);
    q.set("regions", all ? "all" : order.join(","));
    setOpen(false);
    router.push(`/lab/o-report?${q}`);
  };

  return (
    <>
      <button ref={trigger} type="button" onClick={show} aria-haspopup="dialog" aria-expanded={open} aria-describedby={hintId} className="or-region-button">
        {label}
        <svg viewBox="0 0 12 12" aria-hidden><path d="M2 4.2l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      <span id={hintId} className="sr-only">{tr(locale, "region_dialog")}</span>
      {open && host && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(13,27,31,0.45)] p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
          <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId}
            className="max-h-[calc(100dvh-32px)] w-full max-w-[540px] overflow-y-auto rounded-[8px] bg-white p-5 text-left text-[var(--or-ink)] sm:p-7" style={{ letterSpacing: 0 }}>
            <h2 id={titleId} className="text-[21px] leading-tight font-bold">{tr(locale, "region_dialog")}</h2>
            <p className="mt-2 text-[14px] leading-[1.55] font-normal text-[var(--or-slate)]">{tr(locale, "region_hint")}</p>
            <fieldset className="mt-5">
              <legend className="sr-only">{tr(locale, "region_dialog")}</legend>
              <ul className="grid grid-cols-1 gap-x-3 sm:grid-cols-2">
                {options.map((o) => (
                  <li key={o.code}>
                    <label className={`flex h-12 cursor-pointer items-center gap-3 border-b border-[var(--or-line)] px-1 text-[16px] font-medium ${o.count === 0 ? "text-[var(--or-slate)]" : ""}`}>
                      <input type="checkbox" checked={sel.includes(o.code)} onChange={() => toggle(o.code)} className="h-[18px] w-[18px] accent-[var(--or-petrol)]" />
                      <span className="flex-1">{o.label}</span>
                      <span className="or-num text-[13px] font-normal text-[var(--or-slate)]">{tr(locale, "region_count", { n: o.count })}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
            <div className="mt-3 flex gap-4 text-[13px] font-normal">
              <button type="button" onClick={() => setSel(targets)} className="text-[var(--or-petrol)] underline-offset-4 hover:underline">{tr(locale, "region_select_all")}</button>
              <button type="button" onClick={() => setSel([])} className="text-[var(--or-petrol)] underline-offset-4 hover:underline">{tr(locale, "region_clear")}</button>
            </div>
            {warn && <p role="alert" className="mt-3 text-[13px] font-normal text-[var(--or-avoid)]">{tr(locale, "region_none_picked")}</p>}
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={close} className="h-11 rounded-[6px] border border-[var(--or-line-strong)] px-4 text-[14px] font-medium">{tr(locale, "region_cancel")}</button>
              <button type="button" onClick={apply} className="h-11 rounded-[6px] bg-[var(--or-ink)] px-5 text-[14px] font-semibold text-white">{tr(locale, "region_apply")}</button>
            </div>
          </div>
        </div>,
        host,
      )}
    </>
  );
}
