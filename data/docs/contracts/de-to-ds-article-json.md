# DE → DS · 공통 기사 JSON

DE 가 만들고 DS 가 읽는 기사 한 건의 규격. 스키마 원본은 DE 의 [`de/schemas/article_v1.json`](../../de/schemas/article_v1.json)
이고, DS 는 그것을 [`ds/src/hannun/ingest/schema.py`](../../ds/src/hannun/ingest/schema.py) 의 `CommonArticle` 로 읽어
검증한다. 이 문서는 두 쪽이 다르게 알고 있으면 안 되는 것만 적는다.

| 항목 | 내용 |
|---|---|
| 만드는 쪽 | DE (사지한). 신규 기사는 크롤러가, 과거 기사는 CSV 변환기가 만든다 |
| 읽는 쪽 | DS1 (제다빈) `hannun-ingest` → Gold. DS2 는 Gold 를 읽는다 |
| 형태 | JSON 객체 1건. Kafka `news.article.realtime.v1` 메시지이자 HDFS 익스포트의 한 줄(JSONL) |
| DS 가 받는 경로 | **미정** — Kafka 직접 구독인지 HDFS 파일 읽기인지, 파일이면 경로·파티션·주기. DS 코드는 지금 JSON/JSONL 파일만 읽는다 |
| 바꿀 때 | 이 문서와 `article_v1.json` 을 같은 MR 에서 고치고 DS1 을 리뷰어로 넣는다 |

## 필드

DE 스키마 그대로다. DS 열은 DS 가 검증에서 어떻게 다루는지다.

| 필드 | 타입 | null | 뜻 | DS 검증 |
|---|---|---|---|---|
| `schema_version` | string | 아니오 | `"1.0"` | 필수 문자열 |
| `article_id` | string | 아니오 | `sha256:` + SHA-256(`publisher_id\|정규화 URL`) 소문자 hex | 필수. 우리 해시와 비교해 `article_id_verified` 로 기록만 함(아래 정규화 참고) |
| `publisher_id` | string | 아니오 | 내부 언론사 코드 (`yonhap`) | 필수 |
| `publisher_name` | string | 아니오 | 언론사명 | 필수 |
| `source_type` | enum | 아니오 | `DATASET` / `RSS` / `HTML` | 셋만 허용. `HTML` 은 2026-08-28 반영 |
| `url` | string | 아니오 | 원문 URL, 원본 그대로 | 필수 |
| `title` | string | 아니오 | 제목 | 필수, 공백만이면 리젓트 |
| `content` | string | 아니오 | 본문. 크롤러는 100자 미만을 발행 전 폐기 | 필수, 공백만이면 리젓트. **원문 보존** — 정제는 DS 가 `clean` 테이블에 따로 한다 |
| `author` | string | 예 | 기자명 | 빈 문자열은 null 로 정규화 |
| `category` | string | 아니오 | 카테고리 코드. 미제공 시 `OTHER` | 필수 |
| `category_str` | string | 예 | 언론사 원문 분류 (`정치>행정`) | 빈 문자열은 null |
| `thumbnail_url` | string | 예 | 대표 이미지 | 빈 문자열은 null |
| `language` | string | 아니오 | `ko` | 필수 |
| `published_at` | RFC 3339 | 아니오 | **발행 시각**, UTC `Z` | 타임존 없으면 리젓트. 내부는 UTC, 파티션 키 `published_date` 는 UTC 날짜 |
| `crawled_at` | RFC 3339 | 아니오 | 수집 완료 시각. HDFS 파티션 기준 | DS 는 읽지만 Gold 에 저장하지 않는다(모르는 필드로 통과). 필요해지면 Gold 컬럼 추가 |

DS 가 스키마 밖 필드를 만나면 무시한다(에러 아님). DE 가 필드를 더해도 DS 적재는 깨지지 않는다.

## 맞춰야 할 것 — URL 정규화

DE 스키마는 `article_id` 해시 전에 **쿼리스트링과 프래그먼트를 전부 제거**한다(utm 차이로 같은 기사가 다른 id 를
받는 것을 막기 위해). 그런데 과거 CSV 에 있는 언론사 중 **쿼리가 곧 기사 번호**인 곳이 있다:

| 언론사 | URL 꼴 | 쿼리 제거 결과 |
|---|---|---|
| 디지털타임 | `http://www.dt.co.kr/contents.html?article_no=2024010102109919607007` | 3만 건이 전부 `contents.html` 하나 → **같은 id** |
| 국민일보 | `https://www.kmib.co.kr/article/view.asp?arcid=9000004613` | 4만 건이 전부 `view.asp` |
| SBS | `https://news.sbs.co.kr/news/endPage.do?news_id=N9001` | 같은 문제 |

같은 id 를 받으면 Gold 는 첫 건만 남기고 나머지를 "이미 있음" 으로 버린다. DS1 은 **추적 파라미터만 떼는** 규칙
(`utm_source`·`utm_medium`·`utm_campaign`·`utm_term`·`utm_content`·`fbclid`·`gclid` 제거, 나머지 쿼리 유지, 프래그먼트 제거)을
`schema.normalize_url` 에 구현해 두었다. **제안: DE 도 이 규칙으로 바꾼다.** 결정되면 `article_v1.json` 의
`article_id` 설명과 이 절을 함께 고친다. 그 전까지는 쿼리가 있는 URL 에서 `article_id_verified=False` 가 나오고,
그 비율이 조정이 필요한 기사의 양이다.

## 맞춰야 할 것 — 과거 CSV 변환 규칙

과거 기사 CSV 두 개(283만 건, 언론사 34개)의 구조는 [`ds/docs/ds1/DATASET_PROFILE.md`](../../ds/docs/ds1/DATASET_PROFILE.md).
CSV 에는 `publisher_id`·`article_id` 가 없고 `published` 에 타임존이 없어서, 변환 규칙이 정해지지 않으면 DS 검증에서
대량 리젓트된다. DS1 이 개발용으로 만든 변환기 [`ds/scripts/csv_to_common_jsonl.py`](../../ds/scripts/csv_to_common_jsonl.py)
가 아래 제안을 그대로 구현하고 있으니 확정되면 DE 변환기와 맞추거나 가져다 쓴다.

| 항목 | CSV 상태 | 제안 |
|---|---|---|
| `publisher_id` | 없음. `company` 에 언론사명만 | 언론사명 → id 표. 초안은 변환기의 `PUBLISHER_IDS`(34개). `한겨례` 는 데이터셋 오타지만 `hani` 로 |
| `article_id` | 없음 | 위 정규화 규칙으로 `SHA-256(publisher_id\|url)` |
| `published_at` | 형식 4종(`2023-06-23 16:43:33`, `2023-06-16 16:10`, `2023.06.23 16:10`, `2023-01-01 오후 9:40:00`), 타임존 없음 | 전부 **KST** 로 읽어 UTC `Z` 로. 4형식 파서는 변환기 `parse_published` |
| `category` | 언론사 자체 분류(`증권`, `mobile`, `뉴스광장 1부`), 34~41% 빈값 | 정치·경제·사회·국제·스포츠·연예·문화·IT 로 바로 가는 값만 코드로 바꾸고 나머지는 `OTHER`. 원문은 `category_str` 에 보존 |
| `content` 빈값 | 2023 4.8만 건(2.4%), 2024 6.6만 건(8.0%) | 변환 단계에서 버린다(DE 스키마 `minLength: 1`). 개수는 변환 로그에 남긴다 |
| `title` 빈값 | 100건 | 버린다 |
| `link` 중복 | 2023 8.6만 건 | 그대로 변환. `article_id` 가 같아지므로 Gold 가 첫 건만 남긴다 |
| `source_type` | — | `DATASET` |
| `author` | `reporter`, 16~17% 빈값 | 빈값은 null |
| `crawled_at` | 없음 | 변환 실행 시각 |

## DS 가 Gold 에서 파생하는 컬럼

DE 와 무관하지만 DE 가 데이터를 보게 될 때 헷갈리지 않도록 적는다. 공통 JSON 14개 필드 뒤에
`published_date`(UTC 날짜, 파티션 키) · `content_len` · `article_id_verified` · `ingested_at` · `source_ref`(파일:줄) 이 붙는다.
정제 본문은 Gold 가 아니라 `clean/` 테이블의 `content_clean` 이고 `article_id` 로 조인한다.
