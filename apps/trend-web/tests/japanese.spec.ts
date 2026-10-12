import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { tx } from "../components/stage/copy";
import { explainMessage, jaUntranslated, textFor } from "../lib/explain";
import { glossFor } from "../lib/gloss";
import { localeOf, t } from "../lib/i18n";
import { fmtDateTime, listJoin, sourceLabel } from "../lib/labels";
import { SAMPLE_RECORDS } from "../lib/sample/dictionary";

/* 일본어 화면(계획서 ktwoo-copy-flow-and-japanese-ui B). 키가 빠지면 형 검사가 잡는다 — 여기서는 값의 모양(자리표시자·한글 섞임)과
   뜻이 없을 때의 처리를 본다. 용어·문체는 docs/트렌드/일본어-용어집.md */

/** 사전 파일에서 'const <이름> = {' 블록마다 키: 값을 읽는다(한 줄 'key: "value",' 꼴) */
function blocks(file: string): Record<string, Record<string, string>> {
  const out: Record<string, Record<string, string>> = {};
  let cur: Record<string, string> | null = null;
  for (const line of readFileSync(join(__dirname, "..", file), "utf8").split("\n")) {
    const head = line.match(/^const (ko|en|ja)(?::[^=]+)? = \{$/);
    if (head) { cur = out[head[1]] = {}; continue; }
    if (/^\}/.test(line)) { cur = null; continue; }
    const kv = cur && line.match(/^\s+([A-Za-z0-9_]+):\s*("(?:[^"\\]|\\.)*"),?\s*$/);
    if (cur && kv) cur[kv[1]] = JSON.parse(kv[2]);
  }
  return out;
}
const holes = (s: string) => [...s.matchAll(/\{[a-z_]+\}/g)].map((m) => m[0]).sort().join(",");

for (const file of ["lib/i18n.ts", "components/stage/copy.ts"]) {
  test(`${file}: every Japanese string keeps the placeholders and has no Hangul`, () => {
    const { ko, en, ja } = blocks(file);
    expect(Object.keys(ja)).toEqual(Object.keys(en));
    expect(Object.keys(ja).length).toBeGreaterThan(200);
    for (const [k, v] of Object.entries(ja)) {
      expect.soft(v.trim(), k).not.toBe("");
      expect.soft([holes(en[k]), holes(ko[k])], k).toContain(holes(v));
      if (!/[가-힣]/.test(en[k])) expect.soft(v, k).not.toMatch(/[가-힣]/);   // 영어판에 한글이 있는 키(원문 예시)만 한글을 둔다
    }
  });
}

test("glossary terms are written one way only", () => {
  const ja = [...Object.values(blocks("lib/i18n.ts").ja), ...Object.values(blocks("components/stage/copy.ts").ja)].join("\n");
  for (const banned of ["ドラフト", "承認者", "エビデンス", "マーケット", "キャッチコピー", "カテゴリー", "製品"]) expect(ja).not.toContain(banned);
});

test("the cookie value is whitelisted", () => {
  expect(localeOf("ja")).toBe("ja");
  expect(localeOf("en")).toBe("en");
  for (const bad of ["jp", "JA", "", undefined, null, "zh"]) expect(localeOf(bad)).toBe("ko");
});

test("cards show the Japanese gloss, or say it is missing instead of showing Korean", () => {
  const card = { gloss_ko: "뜻", gloss_en: "meaning", gloss_ja: "意味", ja_pending: false };
  expect(glossFor(card, "ja")).toBe("意味");
  expect(glossFor({ ...card, ja_pending: true, gloss_ja: "뜻" }, "ja")).toBe(t("ja", "gloss_ja_pending"));
  expect(glossFor({ gloss_ko: "뜻", gloss_en: "meaning" }, "ja")).toBe(t("ja", "gloss_ja_pending"));   // 예전 서버·캐시에는 gloss_ja 가 없다
  expect(glossFor(card, "en")).toBe("meaning");
  expect(t("ja", "gloss_ja_pending")).toContain("翻訳なし");
});

test("an entry shows the Japanese meaning, or the original with the untranslated notice", () => {
  const lucky = SAMPLE_RECORDS.find((r) => r.term.term_id === "t_luckyvicky")!;
  const jamanchu = SAMPLE_RECORDS.find((r) => r.term.term_id === "t_jamanchu")!;
  expect(jaUntranslated(lucky)).toBe(false);
  expect(textFor(lucky, "ja")?.definition).toBe(lucky.ja?.definition);
  expect(jaUntranslated(jamanchu)).toBe(true);
  expect(textFor(jamanchu, "ja")?.definition).toBe(jamanchu.meanings.at(-1)?.definition);   // 원문(한국어) 그대로
  expect(tx("ja", "tm_untranslated")).toContain("翻訳なし");
  // 원문 뜻이 이미 일본어(가나)면 번역이 없어도 안내하지 않는다
  const jaSource = { ...jamanchu, ja: null, meanings: jamanchu.meanings.map((m) => ({ ...m, definition: "好きなアイドルを応援する活動。" })) };
  expect(jaUntranslated(jaSource)).toBe(false);
});

test("dates, lists and source names follow Japanese conventions", () => {
  expect(fmtDateTime("2026-10-12T05:30:00Z", "ja")).toBe("2026/10/12 14:30");
  expect(fmtDateTime("2026-10-12T05:30:00Z", "ko")).toBe("2026.10.12 14:30");
  expect(listJoin("ja", ["20代", "30代"])).toBe("20代、30代");
  expect(sourceLabel("ja", "ナムウィキ", "記事")).toBe("ナムウィキの記事");
  expect(sourceLabel("ko", "나무위키", "문서")).toBe("나무위키 문서");
});

test("message explanations join the Japanese fragments in Japanese order without spaces", () => {
  const r = explainMessage("週末は「推し活」で遠征", SAMPLE_RECORDS, "ja", null, { nick: "太郎", gen: "50s+" });
  expect(r.items.map((e) => e.record.term.term_id)).toEqual(["t_oshikatsu"]);
  expect(r.greeting).toBe("太郎さん、このメッセージで確認された表現を1件見つけました。");
  expect(r.items[0].notes[0]).toBe("50代以上の利用者にはなじみが薄いかもしれない言葉です。");
  expect(r.items[0].headline).toBe(`「${r.items[0].text?.expansion}」の略。${r.items[0].text?.definition}`);
});
