import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

/* 관리 탭 내용을 읽는 동안 — 머리와 탭은 레이아웃이 그대로 그린다. 반짝이는 뼈대는 쓰지 않는다. */
export default async function AdminLoading() {
  const locale = await getLocale();
  return <p role="status" aria-busy="true" className="text-[13px] text-steel">{t(locale, "adm_loading")}</p>;
}
