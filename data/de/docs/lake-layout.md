# HDFS 레이크 경로 규칙

`/lake/<층>/<데이터종류>/<파티션>` 3단계. 66·68·74 가 각자 다른 경로를 만들지 않도록
여기서 한 번만 정한다.

| 층 | 내용 | 담당 이슈 |
|---|---|---|
| bronze | 소스 원본 그대로 (Kafka value 무변형, jsonl) | S15P21E105-66 |
| silver | 정제·중복 제거, article_v1 스키마, parquet | S15P21E105-68 |
| gold | 서비스 소비용, 비정규화 — 이슈 피드 표 | S15P21E105-69 |

## 현재 경로

- `/lake/bronze/news/ingest_date=YYYY-MM-DD/` — 실시간 기사 원본(Kafka value jsonl). 파티션은 적재일(처리 시점) 기준
- `/lake/bronze/news_dataset/` — SSAFY 데이터셋 CSV 원본 7개 (2019~2025 상반기, `|` 구분)
- `/lake/bronze/bigkinds/` — 빅카인즈 백필 결과 월별 jsonl (2024 하반기·2025 하반기·2026 1~8월, article_v1)
- `/lake/silver/news/dt=YYYY-MM-DD/` — 세 bronze 소스를 합쳐 article_v1 로 통일한 parquet.
  dt 는 published 의 **한국 날짜**(값 자체는 UTC Z). 같은 article_id 는 본문이 긴 것, 동률이면
  crawled_at 최신 하나만 남긴다. DS 는 이 경로만 읽는다 (읽기 전용)
- `/lake/gold/issue_feed/dt=YYYY-MM-DD/` — BE 가 받는 모양으로 합친 이슈 피드. 기사당 한 줄로
  펼쳐 두고 발행기가 이슈 번호로 묶는다. 발행기가 이 표를 읽으므로 어제 것을 다시 보내달라는
  요청에 DS 사슬을 다시 돌리지 않아도 된다
- `/lake/_checkpoints/<잡이름>/` — 스트리밍 체크포인트. 데이터가 아니며,
  지우면 해당 잡이 토픽 처음부터 재적재한다 (bronze 에 중복 발생)

## 규칙

- 새 데이터 종류는 `/lake/bronze/<이름>/` 부터 시작 (예정: 이용로그, S15P21E105-92)
- bronze 는 불변 — 수정·삭제하지 않는다. 정정·중복 제거는 silver 몫
- silver 는 15분마다 오늘·어제 적재분의 dt 파티션만 덮어쓴다. 변환 규칙이 바뀌면
  `bronze_to_silver.py --full` 로 통째로 재구축한다 (실측 3시간 20분)
- `bronze/news` 는 15분 배치가 Kafka 파티션 3개를 각각 써서 하루 200여 개 파일이 된다.
  새벽 정비 DAG(S15P21E105-74)가 어제 파티션을 파일 1개로 합치고 B 서버로 백업한다
- **`bronze/news` 를 읽을 때는 폴더 뿌리가 아니라 `ingest_date=*` 로 읽는다.** 뿌리를
  그대로 읽으면 Spark 가 스트리밍 sink 의 파일 목록 장부(`_spark_metadata`)만 신뢰해서,
  합치기로 바뀐 파일을 놓친다. 장부에는 절대 경로가 적혀 있어 실측에서 엉뚱한 건수가 나왔다
- **복제는 1이다.** 단일 노드라 늘려도 같은 디스크여서 장애 도메인이 하나다. Spark 는
  클라이언트 기본값 3 을 요청하고 그 값이 서버 기본값을 이기므로, `infra/spark/
  spark-defaults.conf` 로 못 박는다. 이게 없으면 "3 개 있어야 하는데 1 개뿐인" 블록이
  쌓여 점검(fsck) 결과가 늘 부족으로 나오고 진짜 문제가 묻힌다
- 백업 대상과 복구 절차는 `docs/backup-restore.md`

## 메달리온 기준에서 감수한 것

정석은 정제와 중복 제거를 silver 가 한 번에 끝내고 소비자가 silver 를 직접 읽는 것이다.
우리는 다음 셋이 어긋나 있고, 이유가 있어 그대로 둔다.

- **정제가 두 곳에 나뉜다.** silver 는 링크 기준 중복만 제거하고, 텍스트 다듬기와 내용이
  비슷한 기사 묶기는 DS 가 한다. DS 가 골든셋으로 점수를 재며 만든 부분이라 옮기면 그 검증을
  다시 해야 한다. 규칙이 어긋나면 이 기록이 단서다
- **소비자가 silver 를 직접 읽지 않는다.** DS 코드가 로컬 파일만 읽어 JSONL 사본을 내려준다.
  `ds_input` 은 silver 의 파생물이며 진실은 silver 다
- **DS 분석 산출물은 레이크 밖에 있다.** DS 가 HDFS 를 쓰지 못하고, 복제 1 단일 노드라
  HDFS 에 둬도 같은 디스크여서 안전해지지 않는다. 사본이 두 벌 되는 것을 피해 로컬에 둔다.
  DS 폴더 이름이 gold 지만 레이크의 gold 와 다르다
