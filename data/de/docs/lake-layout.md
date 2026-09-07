# HDFS 레이크 경로 규칙

`/lake/<층>/<데이터종류>/<파티션>` 3단계. 66·68·74 가 각자 다른 경로를 만들지 않도록
여기서 한 번만 정한다.

| 층 | 내용 | 담당 이슈 |
|---|---|---|
| bronze | 소스 원본 그대로 (Kafka value 무변형, jsonl) | S15P21E105-66 |
| silver | 정제·중복 제거, article_v1 스키마, parquet | S15P21E105-68 |
| gold | 서비스 소비용 — 요구 확정 시 그때 설계 | 미정 |

## 현재 경로

- `/lake/bronze/news/ingest_date=YYYY-MM-DD/` — 실시간 기사 원본(Kafka value jsonl). 파티션은 적재일(처리 시점) 기준
- `/lake/bronze/news_dataset/` — SSAFY 데이터셋 CSV 원본 7개 (2019~2025 상반기, `|` 구분)
- `/lake/bronze/bigkinds/` — 빅카인즈 백필 결과 월별 jsonl (2024 하반기·2025 하반기·2026 1~8월, article_v1)
- `/lake/silver/news/dt=YYYY-MM-DD/` — 세 bronze 소스를 합쳐 article_v1 로 통일한 parquet.
  dt 는 published 의 **한국 날짜**(값 자체는 UTC Z). 같은 article_id 는 본문이 긴 것, 동률이면
  crawled_at 최신 하나만 남긴다. DS 는 이 경로만 읽는다 (읽기 전용)
- `/lake/_checkpoints/<잡이름>/` — 스트리밍 체크포인트. 데이터가 아니며,
  지우면 해당 잡이 토픽 처음부터 재적재한다 (bronze 에 중복 발생)

## 규칙

- 새 데이터 종류는 `/lake/bronze/<이름>/` 부터 시작 (예정: 이용로그, S15P21E105-92)
- bronze 는 불변 — 수정·삭제하지 않는다. 정정·중복 제거는 silver 몫
- silver 는 15분마다 오늘·어제 적재분의 dt 파티션만 덮어쓴다. 변환 규칙이 바뀌면
  `bronze_to_silver.py --full` 로 통째로 재구축한다 (약 1~2시간)
- 15분 배치가 만드는 작은 파일 누적은 새벽 compaction(S15P21E105-74)이 합친다
