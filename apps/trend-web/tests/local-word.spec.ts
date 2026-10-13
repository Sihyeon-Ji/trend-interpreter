import { expect, test } from "@playwright/test";
import { localWord } from "../lib/lang";

/* 화면에 세울 말 — 외국에서 온 말은 그 화면 언어의 원어 이름(백엔드 pipeline/names 가 문서에 글자 그대로 있는 것만 넣는다) */
test("the screen language's original name replaces the headword and drops the reading", () => {
  const gyudon = { canonical: "규동", lang: "ko", names: { ja: "牛丼" }, readings: { ja: "キュドン", en: "gyudong" } };
  expect(localWord(gyudon, "ja")).toEqual({ text: "牛丼", lang: "ja", local: true });
  expect(localWord(gyudon, "en")).toEqual({ text: "규동", lang: "ko", readings: gyudon.readings, local: false });
  expect(localWord({ canonical: "推し活", lang: "ja" }, "ko")).toMatchObject({ text: "推し活", lang: "ja", local: false });
});
