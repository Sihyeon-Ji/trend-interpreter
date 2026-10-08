"use client";

import { useSyncExternalStore } from "react";

const noop = () => () => {};

/* 사전 항목을 불러오지 못했을 때 — 무엇이 안 됐는지 말하고 다시 부를 단추를 준다(언어는 문서의 lang 을 따른다) */
export default function TermError({ reset }: { error: Error; reset: () => void }) {
  const en = useSyncExternalStore(noop, () => document.documentElement.lang === "en", () => false);
  return (
    <section className="rs-stage rs-stage-empty" role="alert">
      <h1 className="rs-lede">{en ? "Couldn't load this entry." : "이 항목을 불러오지 못했어요."}</h1>
      <button type="button" className="rs-btn" data-kind="primary" onClick={reset}>{en ? "Try again" : "다시 불러오기"}</button>
    </section>
  );
}
