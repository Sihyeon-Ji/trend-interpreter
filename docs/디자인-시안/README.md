# 디자인 시안 5안 — 고를 때까지 함께 두고, 고르면 하나만 남긴다

작성일 **2026-10-01** · 상태 **5안 대기 중(팀 회의에서 고름)** · 화면 `/lab`(목록), `/lab/<시안>`

| 시안 | 방향 | 만든 쪽 | 화면 | 설명서 |
| --- | --- | --- | --- | --- |
| 초안 1 `o-report` | 트렌드 리포트형 — 순위 목록·추이 그래프, 오른쪽 미리보기 | Opus 5.5 | `/lab/o-report` | [o-report.md](o-report.md) |
| 초안 2 `o-editorial` | 에디토리얼형 — 이번 주 호처럼 읽는 밈 잡지 | Opus 5.5 | `/lab/o-editorial` | [o-editorial.md](o-editorial.md) |
| 초안 3 `f-report` | 트렌드 리포트형(다른 풀이) | Fable 5.1 | `/lab/f-report` | [f-report.md](f-report.md) |
| 초안 4 `f-editorial` | 에디토리얼형(다른 풀이) | Fable 5.1 | `/lab/f-editorial` | [f-editorial.md](f-editorial.md) |
| 초안 5 `t-studio` | 마케터 스튜디오형 — 우리 브랜드 기준 할 일·근거·쇼츠 제작 키트. **예시 데이터** | 팀원 기획 + Opus 5.5 | `/lab/t-studio` | [t-studio.md](t-studio.md) |

## 폴더 — 시안 하나 = 폴더 넷

시안끼리 서로를 가져다 쓰지 않고, 앱의 다른 화면도 시안을 쓰지 않는다(10-01 확인). 그래서 시안 하나는 아래 네 곳에만 있다.

```
apps/trend-web/app/lab/<시안>/          화면(라우트·레이아웃·CSS·API 라우트)
apps/trend-web/components/lab/<시안>/   화면 조각
apps/trend-web/lib/lab/<시안>/          데이터 가공·문구(index.ts 가 입구)
docs/디자인-시안/<시안>.md               설명서·검토 기록
```

시안들이 함께 쓰는 것은 세 가지뿐이다: `app/lab/page.tsx`(시안 목록), `components/shell-chrome.tsx`(`/lab/*` 에서 앱 틀을 빼는 한 줄), `eslint.config.mjs`(초안 5의 원본 스크립트 `lib/lab/t-studio/source/**` 를 거르는 한 줄 — 초안 5를 지우면 같이 지운다).

## 고른 뒤 할 일

1. 고르지 않은 시안 넷의 폴더 넷을 지운다.
   ```bash
   for d in <지울 시안 넷>; do
     git rm -r apps/trend-web/app/lab/$d apps/trend-web/components/lab/$d apps/trend-web/lib/lab/$d docs/디자인-시안/$d.md
   done
   ```
2. `app/lab/page.tsx` 의 `DRAFTS` 에서 지운 시안 줄을 뺀다(또는 목록 화면째 지운다).
3. 고른 시안을 실제 화면으로 옮긴다 — `app/lab/<시안>` 의 화면을 제자리(`app/` 의 해당 경로)로, `components/lab/<시안>` → `components/`, `lib/lab/<시안>` → `lib/`. 옮긴 뒤 `/lab` 과 `shell-chrome.tsx` 의 `/lab` 예외도 지운다.
4. `pnpm -C apps/trend-web lint && pnpm -C apps/trend-web build` 로 확인한다.
