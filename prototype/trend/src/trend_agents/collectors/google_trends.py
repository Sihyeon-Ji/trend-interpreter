"""Google Trends — 나라별 검색어 순위. 두 경로.

1) BigQuery 공개 데이터셋 `bigquery-public-data.google_trends.international_top_terms / international_top_rising_terms`
   - 약 42개국(KR·JP·ID·TH·VN·TW·IN·AU 포함, SG·HK 없음), 나라·하위지역별 매일 상위 25 + 급상승 25, 5년 백필.
   - 키 없음. ADC(`gcloud auth login --update-adc`) + `GOOGLE_CLOUD_PROJECT`. 무료 1TB/월. 결제 계정 불필요(샌드박스).
   - `rank` 는 나라 안에서 지역·주 무관하게 같다 → DISTINCT rank, term 으로 나라 단위 목록을 만든다.
2) 'Trending now' RSS `https://trends.google.com/trending/rss?geo=KR`
   - 키 없음. 지금 뜨는 검색어 10개 + 대략 검색량 + 관련 뉴스. 어제가 아니라 '지금'.
   - 실측(2026-09-14): JP 피드에 인도네시아어 쿼리가 섞여 있었다. 언어 정합성은 뒤 단계에서 검사.

둘 다 카테고리 라벨이 없다. 카테고리는 로컬 모델(분류만, 뜻 정의 금지)이 붙인다.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, timedelta

import httpx

from ..config import GOOGLE_CLOUD_PROJECT
from ..schemas import TrendQuery

DATASET = "bigquery-public-data.google_trends"
RSS_NS = {"ht": "https://trends.google.com/trending/rss"}
_BQ = None


def _bq():
    """BigQuery 클라이언트는 하나만. ADC 가 없으면 여기서 DefaultCredentialsError 가 난다."""
    global _BQ
    if _BQ is None:
        from google.cloud import bigquery  # ADC 없는 환경(프론트 빌드 등)에서 import 비용을 피한다

        _BQ = bigquery.Client(project=GOOGLE_CLOUD_PROJECT or None)
    return _BQ


def _query(sql: str, params: dict) -> list[dict]:
    from google.cloud import bigquery

    job_params = [
        bigquery.ScalarQueryParameter(k, "DATE" if isinstance(v, date) else "STRING", v) for k, v in params.items()
    ]
    job = _bq().query(sql, job_config=bigquery.QueryJobConfig(query_parameters=job_params))
    return [dict(r) for r in job.result()]


def latest_refresh_date(rising: bool = False) -> date:
    """가장 최근 파티션 날짜 (보통 어제). 파티션 컬럼만 읽어 비용이 거의 없다."""
    table = "international_top_rising_terms" if rising else "international_top_terms"
    rows = _query(
        f"SELECT MAX(refresh_date) AS d FROM `{DATASET}.{table}` WHERE refresh_date >= @since",
        {"since": date.today() - timedelta(days=7)},
    )
    return rows[0]["d"]


def countries(refresh_date: date | None = None) -> list[str]:
    d = refresh_date or latest_refresh_date()
    rows = _query(
        f"SELECT DISTINCT country_code FROM `{DATASET}.international_top_terms` WHERE refresh_date = @d ORDER BY 1",
        {"d": d},
    )
    return [r["country_code"] for r in rows]


def rising_terms(region: str, refresh_date: date | None = None) -> list[TrendQuery]:
    """나라별 급상승 25 (percent_gain 은 전 기간 대비 상승률)."""
    d = refresh_date or latest_refresh_date(rising=True)
    rows = _query(
        f"""SELECT rank, term, MAX(percent_gain) AS percent_gain
            FROM `{DATASET}.international_top_rising_terms`
            WHERE refresh_date = @d AND country_code = @cc
            GROUP BY rank, term ORDER BY rank""",
        {"d": d, "cc": region},
    )
    return [
        TrendQuery(term=r["term"], region=region, rank=r["rank"], source="bq_rising", date=d, percent_gain=r["percent_gain"])
        for r in rows
    ]


def top_terms(region: str, refresh_date: date | None = None) -> list[TrendQuery]:
    """나라별 상위 25. score 는 그 용어의 최신 주 값(0~100, 용어 내 상대값이라 용어끼리 비교 불가)."""
    d = refresh_date or latest_refresh_date()
    rows = _query(
        f"""SELECT rank, term, MAX(score) AS score
            FROM `{DATASET}.international_top_terms`
            WHERE refresh_date = @d AND country_code = @cc
              AND week = (SELECT MAX(week) FROM `{DATASET}.international_top_terms` WHERE refresh_date = @d AND country_code = @cc)
            GROUP BY rank, term ORDER BY rank""",
        {"d": d, "cc": region},
    )
    return [TrendQuery(term=r["term"], region=region, rank=r["rank"], source="bq_top", date=d, score=r["score"]) for r in rows]


def trending_now(region: str, timeout: float = 15.0) -> list[TrendQuery]:
    """'Trending now' RSS. 키 없음. 10건 내외."""
    r = httpx.get(
        "https://trends.google.com/trending/rss", params={"geo": region}, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    out: list[TrendQuery] = []
    for i, it in enumerate(root.findall(".//item"), start=1):
        news = it.find("ht:news_item", RSS_NS)
        out.append(
            TrendQuery(
                term=(it.findtext("title") or "").strip(),
                region=region,
                rank=i,
                source="rss_now",
                date=date.today(),
                approx_traffic=it.findtext("ht:approx_traffic", namespaces=RSS_NS),
                news_title=news.findtext("ht:news_item_title", namespaces=RSS_NS) if news is not None else None,
                news_url=news.findtext("ht:news_item_url", namespaces=RSS_NS) if news is not None else None,
            )
        )
    return out
