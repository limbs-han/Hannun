# EC2 A (J15E105A) 데이터 인프라

단일 노드 HDFS 스택. 크롤러·Spark 적재 잡·Airflow(추가 예정, S15P21E105-106)가 이 위에서 돈다.
Kafka 는 BE 소유(B 서버) — 여기서는 원격 브로커 주소만 참조한다.

## 구성

- `docker-compose.yml` — NameNode + DataNode 1대. 복제 계수 1 (하둡 공식 싱글노드 표준).
  단일 머신에서 복제 2는 같은 디스크에 사본을 두는 가짜 안전이라 쓰지 않는다.
  유실 대비는 새벽 정비 DAG 의 B 서버 백업이 담당 — 대상과 복구 절차는 `docs/backup-restore.md`.
- `hadoop.env` — HDFS 설정 (이미지가 `CORE-SITE.XML_*` 형식 환경변수를 설정 파일로 변환)
- `.env.example` — 환경별 값 (`KAFKA_BROKER`, `HDFS_UI_PORT`). `.env` 로 복사해 사용, 커밋 금지
- `create_topics.sh` — BE Kafka 에 토픽 생성 (자동 생성은 파티션 1 기본값으로 만들어버리므로 금지)
- `smoke_test.sh` — 배포 합격 판정 (HDFS 쓰기/읽기/복제 + Kafka 왕복)
- `airflow/Dockerfile` — Airflow + JDK + pyspark + 크롤러 의존성. Spark 는 별도 클러스터 없이
  DAG 태스크가 `spark-submit --master local[*]` 로 이 컨테이너 안에서 실행
- `postgres` — Airflow 메타DB (LocalExecutor 는 SQLite 미지원)
- B 서버 백업 키는 `~/.ssh/b-airflow.pem`(호스트 소유자 uid 50000)에 두고 읽기 전용으로
  마운트한다. 컨테이너가 uid 50000 으로 돌기 때문에 소유자가 다르면 ssh 가 키를 읽지 못한다.
  사람이 서버에서 직접 쓰는 `~/.ssh/b.pem` 은 계정 소유라 그대로 두고, 이름만 나눠 둔다:
  `sudo cp ~/.ssh/b.pem ~/.ssh/b-airflow.pem && sudo chown 50000:0 ~/.ssh/b-airflow.pem && sudo chmod 600 ~/.ssh/b-airflow.pem`
- **Spark 대기줄**: Spark 를 쓰는 DAG 태스크는 `spark_local` 대기줄(자리 1개)에 세워 한 번에
  하나만 돌게 한다. 드라이버가 airflow 컨테이너 안에서 돌아 메모리가 6GB 로 한정되고, silver 를
  덮어쓰는 중에 읽는 사고도 막아야 한다. 대기줄은 메타DB 에 저장되므로 배포 후 1회만 만든다:
  `docker compose exec airflow airflow pools set spark_local 1 "Spark 드라이버 1개"`
  대기줄이 없으면 해당 태스크가 실행되지 않으니, 메타DB 를 새로 만들면 다시 등록한다
- DS 입력 폴더 `~/ds_input` 도 같은 이유로 소유자를 맞춘다. 호스트에서 읽을 수 있게 755 로 둔다:
  `mkdir -p ~/ds_input && sudo chown 50000:0 ~/ds_input && sudo chmod 755 ~/ds_input`
- DS 입력 전체 내리기는 1회성이라 파이프라인을 멈추고 돌린다. 39GB·2~3시간 예상이며,
  대기줄 자리가 하나라 켜둔 채로 돌리면 15분 배치가 그만큼 밀린다:
  `docker compose exec airflow airflow dags pause bronze_ingest` → `spark-submit ... --bulk` → unpause

## EC2 부트스트랩 (도착 당일)

```bash
# 1. Docker 설치 (Ubuntu)
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu && newgrp docker

# 2. 클론 후 기동
git clone <repo> && cd S15P21E105/data/de/infra
cp .env.example .env   # KAFKA_BROKER=B서버주소:9092, HDFS_UI_PORT=9870 으로 수정
docker compose up -d

# 3. 합격 판정
./smoke_test.sh

# 4. 토픽 생성 (BE Kafka 준비된 뒤 1회)
./create_topics.sh
```

## 메모리

컨테이너별 `mem_limit` 는 EC2 스펙 확인 전 보수치다. 서버에서 `free -h` 확인 후
메모리 예산표(NameNode·DataNode·Airflow·Spark driver 합계 < RAM)에 맞춰 조정할 것.
스왑 미설정 상태면 OOM 이 즉사로 이어지므로 스왑파일 2~4GB 권장:

```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 웹 UI

접속 주소·pem 보관·SSH 터널은 `data/docs/ec2-a-access.md` 참고.
HDFS UI(9870)와 Airflow UI(8080)는 모두 compose 에서 서버 내부 전용(127.0.0.1)으로 묶여 있어
SSH 터널로만 접속한다. Airflow 화면에서 DAG 를 돌릴 수 있어 사실상 실행 권한이며, DS 실행 환경이
도커를 부르게 되면 그 권한이 서버 관리자 권한까지 닿기 때문이다.

## 전 구간 검증

Airflow 웹 UI 에서 `spark_smoke` DAG 수동 트리거 → 성공이면 Airflow→Spark→HDFS 정상.
CLI 로는 `docker compose exec airflow airflow dags trigger spark_smoke`
