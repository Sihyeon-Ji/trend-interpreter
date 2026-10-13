import { expect, test } from "@playwright/test";
import { localWord, originalName } from "../lib/lang";

/* 화면에 세울 말 — 외국에서 온 말은 그 화면 언어의 원어 이름(백엔드 pipeline/names 가 문서에 글자 그대로 있는 것만 넣는다) */
test("the screen language's original name replaces the headword and drops the reading", () => {
  const gyudon = { canonical: "규동", lang: "ko", names: { ja: "牛丼" }, readings: { ja: "キュドン", en: "gyudong" } };
  expect(localWord(gyudon, "ja")).toEqual({ text: "牛丼", lang: "ja", local: true });
  expect(localWord(gyudon, "en")).toEqual({ text: "규동", lang: "ko", readings: gyudon.readings, local: false });
  expect(localWord({ canonical: "推し活", lang: "ja" }, "ko")).toMatchObject({ text: "推し活", lang: "ja", local: false });
});

test("a word from an English-speaking country shows its English original on screens other than Korean", () => {
  const goblin = { canonical: "고블린 모드", lang: "ko", names: { en: "goblin mode" }, readings: { ja: "ゴブリン モード" } };
  expect(localWord(goblin, "ja")).toEqual({ text: "goblin mode", lang: "en", local: true });   // 한글·가타카나 읽기 대신 원어
  expect(localWord(goblin, "ko")).toMatchObject({ text: "고블린 모드", local: false });
  expect(originalName(goblin.names)).toEqual({ lang: "en", name: "goblin mode" });
  expect(originalName({ ja: "牛丼", en: "gyudon" })).toEqual({ lang: "ja", name: "牛丼" });
});

test("a reference title drops the site name in front, which the source column already gives in the screen language", async () => {
  const { cleanSource } = await import("../lib/sources");
  const e = { evidence_id: "e1", kind: "wiki", url: "https://namu.wiki/w/x", source_domain: "namu.wiki", observed_at: "2026-10-01T00:00:00Z",
    title: "나무위키: 제로투 회피 (CC BY-NC-SA 2.0 KR)", excerpt: "" } as const;
  const row = cleanSource(e as never, "제로투", "ja");
  expect(row.title).toBe("제로투 회피 (CC BY-NC-SA 2.0 KR)");          // 문서 제목·라이선스는 그대로
  expect(row.source).toBe("ナムウィキの記事");
});
