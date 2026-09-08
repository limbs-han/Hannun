# 공통 기사 JSON (article_v1)

DE 가 적재한 기사를 DS 가 읽을 때의 규격. 원본 정의는
`data/de/schemas/article_v1.json` (JSON Schema) 하나이고 이 문서는 요약이다.

2026-08-31 개정: 필드명을 SSAFY 데이터셋 CSV·Kafka 유통 8필드와 동일하게
바꿨다. BE 크롤링 문서 §3 의 옛 이름(publisher_name, url, content, author,
published_at)은 더 이상 쓰지 않는다.

## 필드

| 필드 | 타입 | null | 의미 |
| --- | --- | --- | --- |
| company | string | X | 언론사명, 한글 원문 (예: 연합뉴스) |
| title | string | X | 기사 제목 |
| link | string | X | 기사 원문 URL, 원본 그대로 |
| published | string | X | 발행 시각. UTC RFC 3339, `Z` 종결만 허용 (원본 KST 에서 -9h 변환됨) |
| category | string | X | 카테고리 원문 문자열. 원본 결측이면 `OTHER` |
| category_str | string | O | 카테고리 전체 경로 (예: 뉴스 > 문화) |
| reporter | string | O | 기자명, 여러 명이면 원문 표기 그대로 |
| article | string | X | 본문 |
| schema_version | string | X | `1.0` 고정 |
| article_id | string | X | `sha256:` + SHA-256(publisher_id + "\|" + 정규화 link). 정규화 규칙은 스키마 참조 |
| publisher_id | string | X | 내부 언론사 코드 (예: yonhap) |
| source_type | string | X | `DATASET` / `RSS` / `HTML` |
| language | string | X | 언어 코드 (예: ko) |
| thumbnail_url | string | O | 대표 이미지 URL. 데이터셋 반입분은 null |
| crawled_at | string | X | 수집 시각. UTC RFC 3339, `Z` 종결. 파티션·신선도 기준 |

## 읽는 위치 (2026-09-07, S15P21E105-68)

- HDFS `/lake/silver/news/dt=YYYY-MM-DD/` parquet. 위 15필드에 파티션 컬럼 `dt`(published 의
  한국 날짜)가 따라온다. 데이터셋·빅카인즈·실시간 세 소스가 합쳐져 있고 article_id 중복은
  제거돼 있다. 실시간분은 15분마다 오늘·어제 dt 가 갱신된다
- silver·bronze 는 **읽기 전용**이다. DS 산출물은 별도 경로에 쓴다
- HDFS 접속 시 `HADOOP_USER_NAME=root` 를 선언하지 않는다. root 는 적재 잡 전용이며 DS 가
  같은 이름으로 쓰면 실수로 레이크를 덮어쓸 수 있다
- 실시간분의 `crawled_at` 은 적재일 자정으로 근사한 값이다. 초 단위 수집 시각이 필요하면 DE 에 요청

## DS 파이프라인 입력 (S15P21E105-118)

DS 파이프라인은 로컬 파일만 읽으므로 DE 가 silver 를 JSONL 로 풀어 A 서버에 내려둔다.

- 경로: `/home/ubuntu/ds_input/<YYYY>/<YYYY-MM-DD>.jsonl` (비압축, 한 줄에 기사 하나)
- **하루는 항상 파일 하나다.** 조각으로 나뉘어도 DE 가 이어붙여 하나로 만든다
- 하루 단위 배치는 DE 내부 사정이다. **뿌리나 연도를 가리켜 읽는 것을 권한다** — 그러면 배치가
  바뀌어도 읽는 쪽이 흔들리지 않는다
- 날짜는 발행 시각의 **한국 날짜**다. silver 의 dt 파티션과 같은 기준이며 파일 안 시각은 UTC 다
- 필드는 위 표의 15개 그대로다. 파티션 컬럼 `dt` 는 넣지 않는다
- 매일 04:00 KST 에 갱신된다. **내용이 바뀐 날짜의 파일은 날짜가 얼마나 지났든 다시 쓰인다.**
  RSS 가 몇 달 전 기사를 뒤늦게 주면 그 옛 날짜 파일도 다시 쓰인다. 어느 날짜가 바뀌었는지는
  파일 변경 시각으로 알 수 있다. 같은 창을 다시 처리해도 안전해야 한다
- 다른 기간이 필요하면 DE 에 요청한다. 날짜 구간으로 내려줄 수 있다

## 알아둘 것

- `published` 는 UTC 다. KST 로 보려면 +9h. 패턴이 `Z` 종결을 강제하므로
  KST 문자열이 섞이면 검증에서 거부된다.
- `category` 는 enum 이 아니다. 사회·정치 같은 섹션명과 뉴스 9 같은 방송
  프로그램명이 섞여 있고, 결측률이 기간마다 다르다 (2024 상반기 41%,
  2025 상반기 20%, KBS뉴스·머니S·한국경제TV 는 전량 `OTHER`).
- 갱신 주기: 실시간분 15분 배치, 과거분은 반입 시.

## DS 반영 상태 (2026-08-31 완료)

DS 는 필드를 **개명하지 않고 입력 경계에서 흡수한다** — `CommonArticle` 이 새 이름과
옛 이름을 모두 받고(company→publisher_name, link→url, article→content,
reporter→author, published→published_at), Gold 컬럼·정제/중복 테이블·DS1→DS2
출력은 기존 이름 그대로다. 입력 계약이 또 바뀌어도 하류가 흔들리지 않게 하기 위한
구조라 앞으로도 유지한다.

- URL 정규화(프래그먼트 제거 → 추적 파라미터 12개 제거 → 남은 쿼리 정렬)는 DS 의
  `schema.normalize_url` 이 스키마와 같은 규칙을 구현하고, 받은 `article_id` 를
  재계산해 대조한 결과를 Gold 에 `article_id_verified` 로 남긴다.
- `source_type` 의 `HTML`, `category` 의 `OTHER` 채움·원문 문자열 규칙은 반영돼 있다.
- `crawled_at` 은 읽되 Gold 에 저장하지 않는다. 필요해지면 컬럼을 추가한다.

계약을 바꾸는 MR 에는 읽는 쪽(DS)을 리뷰어로 넣는다.
