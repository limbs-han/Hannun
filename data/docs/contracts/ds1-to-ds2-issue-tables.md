# DS1 → DS2 · 이슈 군집 테이블 계약

DS2(관점 대조·키워드)가 소비하는 DS1 산출물의 위치·스키마·주의. 저장은 전부
parquet 이고 `hannun` 패키지의 스토어 클래스로 읽는다 (경로 문자열 조립 금지 —
파티션 규칙이 스토어 안에 있다).

## 1. 어디에 있나

| 테이블 | 위치 | 단위 | 읽기 |
|---|---|---|---|
| 기사→이슈 배정 (최종) | `<root>/issue_quality/` | 기사, 발행일(UTC) 파티션 | `QualityStore(root).read(start, end)` |
| 이슈 카드 (대표·화제성) | `<root>/issue_summary/` | 이슈, 창 파티션 | `SummaryStore(root).read(window_start)` |
| 기사→서비스 이슈 ID | `<root>/issue_registry/` | 기사, 창 파티션 | `RegistryStore(root).read_window(window_start)` |

root: EC2 운영 `/home/ubuntu/gold`, 로컬 개발은 각자 gold 루트.
갱신: 매일 04:30 KST 일일 배치가 최근 48h 창을 재계산한다.

## 2. 핵심 컬럼

**issue_quality** (기사 단위 — DS2 의 주 입력)

| 컬럼 | 뜻 |
|---|---|
| `article_id` | gold·clean 과 조인 키 |
| `issue_local` | 이슈 번호. **창 안에서만 유효한 임시 번호**, -1 은 노이즈 |
| `structured` | 정형(시황·인사 등 템플릿) 이슈 소속 — **관점 분석 대상에서 제외 권장** |
| `rescued` | 노이즈였다가 구제 배정된 기사 |

**issue_summary** (이슈 단위)

| 컬럼 | 뜻 |
|---|---|
| `issue_local` / `issue_id` | 임시 번호 / 승계되는 서비스 ID |
| `representative` | 대표 기사 article_id (이슈 중심 최근접) |
| `issue_size` · `publishers` · `hot_score` | 규모 · 언론사 수 · 화제성(피드 정렬 키) |
| `first/last_published_at` | 이슈 시간 범위 (UTC) |

**issue_registry**: `article_id → issue_id`. 날짜를 넘나드는 추적은 `issue_local`
이 아니라 **`issue_id`** 로 — 재군집마다 issue_local 은 리셋되고 issue_id 가 승계된다.

## 3. 읽기 예시

```python
from hannun.quality import QualityStore
from hannun.feed import SummaryStore
from hannun.ingest import GoldStore

root = "/home/ubuntu/gold"
q = QualityStore(root).read("2026-09-07", "2026-09-08")
members = q[(q.issue_local >= 0) & (~q.structured)]          # 분석 대상
gold = GoldStore(root).read("2026-09-07", "2026-09-08",
                            columns=["article_id", "title", "content"])
per_issue = members.merge(gold, on="article_id").groupby("issue_local")
```

## 4. 주의

1. 파티션 날짜는 **UTC 발행일** — KST 하루는 UTC 이틀에 걸친다
2. `issue_local` 을 저장·전달 키로 쓰지 말 것 (창마다 리셋). 지속 키는 `issue_id`
3. 본문은 `CleanStore`(`content_clean`) 권장 — 실수집 UI 잔재가 정제돼 있다
4. 노이즈(-1)·정형(structured) 처리 정책은 소비 쪽 선택이지만, 관점 분석은 둘 다
   제외를 권장 (근거: 티켓 93·104 실측)

## 5. 역방향 (DS2 → 서비스/DS1) — 제안

DS2 산출(관점·키워드)은 아래 키로 붙이는 것을 제안한다. 합의 후 이 절을 확정한다.

- 기사 단위 산출(관점 라벨): `article_id` 키 — 어떤 창과도 무관하게 유효
- 이슈 단위 산출(키워드·관점 분포): `(window_start, issue_local)` 또는 `issue_id` 키.
  서비스 노출용이면 **issue_id 권장** (창을 넘어 유지)
