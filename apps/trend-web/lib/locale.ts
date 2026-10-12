import { cookies } from "next/headers";
import { LOCALE_COOKIE, koOrEn, localeOf, type LabLocale, type Locale } from "./i18n";

/** 서버 컴포넌트에서 현재 언어. 쿠키가 없거나 모르는 값이면 한국어. */
export async function getLocale(): Promise<Locale> {
  return localeOf((await cookies()).get(LOCALE_COOKIE)?.value);
}

/** 디자인 시안(/lab/*)의 언어 — 시안은 한국어·영어뿐이라 일본어는 영어로. */
export async function getLabLocale(): Promise<LabLocale> {
  return koOrEn(await getLocale());
}
