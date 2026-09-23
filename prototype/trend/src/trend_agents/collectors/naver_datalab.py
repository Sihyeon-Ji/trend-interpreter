"""네이버 데이터랩 — 검색어 트렌드(연령·성별·기기별 검색 곡선)와 쇼핑인사이트(분야별 클릭 트렌드). **한국 한정 세대 신호.**

2026-07-30 부터 개발자센터(openapi.naver.com) 신규 등록이 막히고 **NAVER API HUB**(네이버 클라우드)로 옮겨졌다.
- HUB(기본):  https://naverapihub.apigw.ntruss.com, 헤더 X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY. 한시 무료, 데이터랩 API 각 월 5만 회, 50 RPS.
- 구 개발자센터(NAVER_API_HUB=0, 2027-06-30 까지 기존 키만): https://openapi.naver.com, X-Naver-Client-Id / X-Naver-Client-Secret.

제약: 값은 '요청 안에서' 최대 100 으로 정규화된 상대 지수. 요청이 다르면 절대 비교 불가 → 세대 간 크기 비교는 못 하고
'어느 세대에서 먼저/언제 튀었나'(spike 시점)만 본다.
"""
from __future__ import annotations

import httpx

from ..config import NAVER_API_HUB, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, require

HUB = "https://naverapihub.apigw.ntruss.com"
LEGACY = "https://openapi.naver.com"
# 세대 → 데이터랩 연령 코드 (검색어 트렌드: 1=0-12, 2=13-18, 3=19-24, 4=25-29, 5=30-34, ... 11=60+)
AGE_BUCKETS = {"10s": ["2"], "20s": ["3", "4"], "30s": ["5", "6"], "40s": ["7", "8"], "50s+": ["9", "10", "11"]}
# 쇼핑인사이트 분야 코드
SHOPPING_CATEGORIES = {"패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002", "디지털/가전": "50000003", "식품": "50000008"}


def _headers() -> dict:
    cid = require("NAVER_CLIENT_ID", NAVER_CLIENT_ID)
    sec = require("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET)
    if NAVER_API_HUB:
        return {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec, "Content-Type": "application/json"}
    return {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec, "Content-Type": "application/json"}


def _post(path_hub: str, path_legacy: str, body: dict) -> dict:
    url = (HUB + path_hub) if NAVER_API_HUB else (LEGACY + path_legacy)
    r = httpx.post(url, json=body, headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def search_trend(keywords: list[str], start: str, end: str, ages: list[str] | None = None, time_unit: str = "date",
                 gender: str | None = None, device: str | None = None) -> dict:
    """keywords(최대 5개) 각각을 그룹 하나로. ages 는 데이터랩 코드 리스트(None=전체)."""
    body: dict = {"startDate": start, "endDate": end, "timeUnit": time_unit, "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords[:5]]}
    if ages:
        body["ages"] = ages
    if gender:
        body["gender"] = gender
    if device:
        body["device"] = device
    return _post("/search-trend/v1/search", "/v1/datalab/search", body)


def spike_by_generation(keyword: str, start: str, end: str) -> dict[str, dict]:
    """세대별로 요청을 나눠 keyword 의 피크 날짜와 곡선을 돌려준다. 5회 호출."""
    out: dict[str, dict] = {}
    for gen, codes in AGE_BUCKETS.items():
        pts = search_trend([keyword], start, end, ages=codes)["results"][0]["data"]
        peak = max(pts, key=lambda p: p["ratio"]) if pts else None
        out[gen] = {"peak_date": peak["period"] if peak else None, "points": pts}
    return out


def shopping_categories(categories: dict[str, str], start: str, end: str, time_unit: str = "week",
                        ages: list[str] | None = None, gender: str | None = None, device: str | None = None) -> dict:
    """분야별 클릭 트렌드 (최대 3개 분야). ages 는 쇼핑인사이트 코드("10","20",...,"60")."""
    body: dict = {"startDate": start, "endDate": end, "timeUnit": time_unit, "category": [{"name": n, "param": [c]} for n, c in list(categories.items())[:3]]}
    if ages:
        body["ages"] = ages
    if gender:
        body["gender"] = gender
    if device:
        body["device"] = device
    return _post("/shopping/v1/categories", "/v1/datalab/shopping/categories", body)


def shopping_category_age(category_code: str, start: str, end: str, ages: list[str] = ("10", "20", "30", "40", "50", "60"), time_unit: str = "week") -> dict:
    """한 분야 안의 연령별 클릭 트렌드. (HUB 경로는 문서에 예시가 없어 옛 경로 규칙을 따름 — 실패하면 shopping_categories 를 연령별로 나눠 부른다.)"""
    body = {"startDate": start, "endDate": end, "timeUnit": time_unit, "category": category_code, "ages": list(ages)}
    try:
        return _post("/shopping/v1/category/age", "/v1/datalab/shopping/category/age", body)
    except httpx.HTTPStatusError:
        out = {"results": []}
        for a in ages:
            r = shopping_categories({category_code: category_code}, start, end, time_unit, ages=[a])
            out["results"].append({"title": a, "data": r["results"][0]["data"] if r.get("results") else []})
        return out
