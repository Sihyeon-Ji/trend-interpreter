import { cookies } from "next/headers";
import { LOCALE_COOKIE, type Locale } from "./i18n";

/** 서버 컴포넌트에서 현재 언어. 쿠키가 없으면 한국어. */
export async function getLocale(): Promise<Locale> {
  const v = (await cookies()).get(LOCALE_COOKIE)?.value;
  return v === "en" ? "en" : "ko";
}
