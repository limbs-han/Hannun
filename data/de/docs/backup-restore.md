# 백업과 복구 (S15P21E105-74)

## 무엇을 지키고 무엇을 지키지 않는가

백업 대상은 "잃으면 되돌릴 길이 없는 것"으로 한정한다. 60GB 전부를 매일 복사하는 대신
하루 수십 MB 만 보내는 이유다.

| 데이터 | 유실되면 | 백업 |
|---|---|---|
| `bronze/news` 실시간 기사 | Kafka 보관 7일이 지나면 되받을 길 없음 | 매일 |
| 수집기 `seen.sqlite` | 지난 기사를 다시 발행 | 매일 |
| `bronze/bigkinds` 4.3GB | 빅카인즈 재다운로드 + 본문 재수집 3일 | 1회 수동 |
| `backfill_jobs.sqlite` | 위와 같음 | 1회 수동 |
| `bronze/news_dataset` 23GB | 로컬 PC 에 원본 CSV 있음, 재반입 1시간 | 안 함 |
| `silver` 15GB | `bronze_to_silver.py --full` 로 재구축 3시간 20분 | 안 함 |

## 매일 백업

`nightly_maintenance` DAG 가 03:00 KST 에 어제 파티션을 합친 뒤 B 서버로 보낸다.
목적지는 `ubuntu@j15e105.p.ssafy.io:/home/ubuntu/backup/de/<날짜>/`, 보관 30일.

- 받는 쪽에서 sha256 을 대조하고, 어긋나면 태스크가 실패한다. 보낸 파일이 아니라 도착한
  파일이 온전한지가 중요하다
- 전송은 `--bwlimit` 20MB/s 로 묶어 B 의 서비스 트래픽과 겹치지 않게 한다
- B 가 쓰는 자원은 디스크뿐이다. 하루 약 4MB × 30일이면 120MB 안쪽이고, rsync 는 파일을
  통째로 메모리에 올리지 않아 크기와 무관하게 수십 MB 만 쓴다

## 키 관리

전송 키는 `~/secrets/b.pem` 에 두고 컨테이너에 읽기 전용으로 마운트한다. 컨테이너가
uid 50000 으로 돌기 때문에 **호스트 파일 소유자도 50000 이어야** ssh 가 키를 읽는다.

```bash
mkdir -p ~/secrets && cp ~/.ssh/b.pem ~/secrets/b.pem
sudo chown 50000:0 ~/secrets/b.pem && sudo chmod 600 ~/secrets/b.pem
```

## 복구 절차

2026-09-08 에 아래 절차로 실제 복구를 확인했다 (2,259줄 왕복 일치).

```bash
# 1. B 에 어떤 날짜가 있는지 본다
ssh -i ~/.ssh/b.pem ubuntu@j15e105.p.ssafy.io "ls /home/ubuntu/backup/de/"

# 2. 받아서 무결성부터 확인한다
DAY=2026-09-06
docker compose exec airflow bash -c "
  scp -i /opt/airflow/.ssh/b.pem ubuntu@j15e105.p.ssafy.io:/home/ubuntu/backup/de/$DAY/'*' /tmp/ &&
  cd /tmp && sha256sum -c SHA256SUMS --quiet && echo 무결성OK"

# 3. 줄 수를 눈으로 확인한 뒤 HDFS 로 되돌린다. 먼저 별도 경로에 풀어 확인하고,
#    운영 경로를 덮는 것은 마지막에 한다
docker compose exec airflow bash -c "gzip -dc /tmp/news_$DAY.tar.gz | wc -l"
docker exec -i infra-namenode-1 bash -c "
  hdfs dfs -mkdir -p /lake/bronze/news/ingest_date=$DAY &&
  hdfs dfs -put - /lake/bronze/news/ingest_date=$DAY/part-00000-restored.c000.txt" \
  < <(docker compose exec -T airflow gzip -dc /tmp/news_$DAY.tar.gz)

# 4. silver 를 그 날짜만 다시 만든다
docker compose exec airflow spark-submit --master 'local[*]' \
  /opt/airflow/jobs/bronze_to_silver.py --ingest-dates $DAY
```

`seen.sqlite` 는 `gzip -dc seen.sqlite.gz > /opt/airflow/state/seen.sqlite` 로 되돌린다.
되돌리기 전에 크롤러 DAG 를 끈다 — 실행 중에 바꾸면 수집기가 파일을 붙잡고 있다.

## 지키지 않는 것을 잃었을 때

- `silver`: `bronze_to_silver.py --full`. 3시간 20분, DAG 를 멈추고 돌린다
- `bronze/news_dataset`: 로컬 PC 의 `news_dataset/*.csv` 를 다시 올린다
- `bronze/bigkinds`: 1회 수동 백업본이 B 에 있다. 없으면 빅카인즈 재다운로드부터다
