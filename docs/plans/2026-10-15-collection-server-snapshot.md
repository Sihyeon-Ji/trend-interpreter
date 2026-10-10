# 10-15 수집 서버 스냅숏 – 마지막 운영 DB 갱신 전 준비

실행일 **2026-10-15 밤까지**(fit 단계 빼기는 지금부터) · 담당 **ktwoo** · 상태 **시작 전** · 다음 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md)(shji)

[계획 목록](README.md) · 갱신 절차 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md#절차) · 일본 후보 보강 [밈 추천 남은 일](ktwoo-meme-recommendation-remaining.md#21-빈-시장--일본-화장품러닝화가계부-한국-화장품-추천-0)

## 1. 왜 하나

10-16에 수집 서버의 최신 스냅숏(`db/latest`)으로 운영 DB를 마지막으로 새로 만든다. 그 전에 서버 파이프라인이 질 낮은 쓰임 낱말을 채우지 않게 하고, 일본 시장 후보를 보강하고, 스냅숏을 제때 올려야 한다.

## 2. 지금 상태 (10-10, 운영 DB 사본 기준)

- 쓰임 낱말(`term_fit`)이 붙은 말 7,893개 중 7,599개는 로컬 `gemma4:e4b`가 붙인 옛 값이라 `audience`(누가 알아듣나)·`kind`(밈 종류) 칸이 비어 있다. 두 칸은 10-09에 생겼다(커밋 f0959b1·e89a3a5).
- fit 단계는 두 칸이 빈 행을 다시 붙인다. 서버에서는 로컬 Gemma로 **매 실행 40개씩** 붙는다.
- 추천 후보는 이미 Gemini Flash(233개)와 사람 고정(61개, `human:지시현`)으로 붙어 있다. 10-09에 몰아 붙이기는 Gemini로 하기로 정했다(`fit_backfill.py --gemini`, 사용자 결정). 운영 갱신은 이 값을 운영 DB에서 이어 받는다(`refresh_production.carry_fits`).
- **문제:** 서버가 e4b로 채운 값은 칸이 차 있어 다시 붙지 않고, `--gemini` 몰아 붙이기도 건너뛴다. e4b는 사용층 판정이 거의 나오지 않았다(210개 중 niche 1개). 10-16 스냅숏에서 새로 추천 후보가 된 말이 이 값으로 남는다.

## 3. 할 일

1. **develop 받기.** 최신 develop을 받는다. 서버와 관련된 변경은 쓰임 낱말의 `audience`·`kind` 칸, 리스크 민감 소재 규칙 수정, 쓰임 낱말 몰아 붙이기 옵션(`--gemini`·`--batch`)이다.
2. **fit 단계 빼고 돌리기 (10-16 갱신까지).** 파이프라인을 fit 없이 돌린다.
   ```
   uv run scripts/run_pipeline.py --loop --stages collect,classify,spikes,interpret,candidates,spot,namu,trendaword,hunt,research,crosscheck,audit,track,risk,naver,translate,topics,board,dashboard
   ```
   이미 e4b로 새로 채운 행이 있으면 개수를 알려 준다.
   ```
   SELECT count(*) FROM term_fit WHERE model LIKE 'local:%' AND json::json->>'kind' IS NOT NULL;
   ```
3. **일본 후보 보강 (할 수 있으면).** 일본 뉴스·pixiv 백과·위키백과 분류에서 화장품·패션·금융·생활 분야의 지금 쓰이는 말을 더 모은다. 지금 일본 카드는 46개이고 27개가 식어 가는 말, 나머지도 대부분 엔터 분야다. 상세는 [밈 추천 남은 일 §2.1](ktwoo-meme-recommendation-remaining.md#21-빈-시장--일본-화장품러닝화가계부-한국-화장품-추천-0).
4. **스냅숏 올리기 – 10-15 밤까지.** 3을 하면 그 수집·조사가 끝난 뒤 `db/latest`를 올리고, 올린 시각(`updated_at.txt`)을 shji에게 알린다. 그 뒤 10-16 갱신까지는 올리지 않는다(갱신 중에 바뀌지 않게).

## 4. 서버에서 하지 않는 것

- 쓰임 낱말 몰아 붙이기(`fit_backfill.py`)를 로컬 모델로 돌리지 않는다. 새 추천 후보는 갱신 때 shji가 Gemini로 붙인다.
- 리스크 규칙 수정은 갱신 때 규칙 단계를 다시 돌리면 반영된다.
- 운영에서 사람이 정한 것(사전에서 뺀 말, 리스크 결정, 쓰임 낱말 고정, 뜻 수정)은 갱신 때 운영 DB에서 이어 받는다.

## 5. 완료 기준

- 10-15 밤까지 `db/latest`가 올라왔고, 그 스냅숏에 fit 단계가 10-10 뒤로 붙인 e4b 값이 없다(또는 개수를 알렸다).
- 일본 보강을 했다면 보강 전후 일본 카드 수를 알렸다.
