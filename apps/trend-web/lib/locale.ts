import { cookies, headers } from "next/headers";
import { LOCALE_COOKIE, isLocale, koOrEn, localeFromAcceptLanguage, type LabLocale, type Locale } from "./i18n";

/** 서버 컴포넌트에서 현재 언어. 고른 언어(쿠키)가 먼저, 없으면 브라우저 언어(Accept-Language) — 그것도 없으면 한국어. */
export async function getLocale(): Promise<Locale> {
  const saved = (await cookies()).get(LOCALE_COOKIE)?.value;
  if (isLocale(saved)) return saved;
  return localeFromAcceptLanguage((await headers()).get("accept-language"));
}

/** 디자인 시안(/lab/*)의 언어 — 시안은 한국어·영어뿐이라 일본어는 영어로. */
export async function getLabLocale(): Promise<LabLocale> {
  return koOrEn(await getLocale());
}
