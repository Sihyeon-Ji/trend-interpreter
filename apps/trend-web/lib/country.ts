/* 나라 화면(/country/[code])이 열리는 코드 — 이름을 아는 나라만. 전 세계(GLOBAL)는 나라가 아니고, 중국 본토는 서비스 범위 밖이다(ADR 0001). */
import { L } from "./labels";

export const isCountryCode = (code: string) => code !== "GLOBAL" && code !== "CN" && Object.hasOwn(L("ko").region, code);

/** 나라 화면 '검색이 늘어난 이유' 행의 id — 최근 변화의 검색 급증 행이 여기로 곧장 간다 */
export const whyAnchor = (term: string) => `why-${term.trim().toLowerCase().replace(/\s+/g, "-")}`;
