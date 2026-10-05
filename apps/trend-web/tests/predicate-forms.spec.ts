import { expect, test } from "@playwright/test";
import { predicateForms, termPattern } from "../lib/explain";

test("predicate headwords match their inflected forms like the backend matcher", () => {
  const hits = (term: string, text: string) => termPattern(term).test(text);
  expect(hits("찰지다", "찰진 맛")).toBe(true);
  expect(hits("짜치다", "짜쳤다")).toBe(true);
  expect(hits("열받다", "완전 열받네")).toBe(true);
  expect(hits("마렵다", "여행 마려운 날")).toBe(true);
  expect(hits("폭룡적이다", "폭룡적인 굿즈")).toBe(true);
  expect(hits("고능하다", "고능해")).toBe(true);
  expect(termPattern("열받다").exec("완전 열받네 ㅋㅋ")?.[0]).toBe("열받네");
  expect(hits("찰지다", "찰흙")).toBe(false);
  expect(hits("짜치다", "짜증")).toBe(false);
  expect(hits("사건이다", "사건인데")).toBe(false);
  // the same regex body as match.predicate_forms
  expect(predicateForms("찰지다")).toBe("찰(?:져|졌|지|진|질|짐|집)[가-힣]*");
  expect(predicateForms("고능하다")).toBe("고능(?:하|한|할|함|합|해|했)[가-힣]*");
  expect(predicateForms("마렵다")).toBe("마(?:렵|려(?=[우워운울]))[가-힣]*");
  expect(predicateForms("디토합니다")).toBeNull();
});
