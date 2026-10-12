import { expect, test } from "@playwright/test";
import { writableIn } from "../lib/lang";

test("the start stage keeps each market's words in its own script, like the drafts rule", () => {
  expect(writableIn("건어물녀", "JP")).toBe(false);      // 일본 칸에 한글 표기 말이 섰다(10-12 리허설)
  expect(writableIn("推し活", "JP")).toBe(true);
  expect(writableIn("Nice boat", "JP")).toBe(true);     // 라틴 글자는 어느 시장에서나 쓴다
  expect(writableIn("推し活", "KR")).toBe(false);
  expect(writableIn("인정", "KR")).toBe(true);
  expect(writableIn("인정", "GLOBAL")).toBe(false);
  expect(writableIn("Pokémon", "GLOBAL")).toBe(true);
});
