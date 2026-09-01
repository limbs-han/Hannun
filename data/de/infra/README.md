# EC2 A (J15E105A) 데이터 인프라

단일 노드 HDFS 스택. 크롤러·Spark 적재 잡·Airflow(추가 예정, S15P21E105-106)가 이 위에서 돈다.
Kafka 는 BE 소유(B 서버) — 여기서는 원격 브로커 주소만 참조한다.

## 구성

- `docker-compose.yml` — NameNode + DataNode 1대. 복제 계수 1 (하둡 공식 싱글노드 표준).
  단일 머신에서 복제 2는 같은 디스크에 사본을 두는 가짜 안전이라 쓰지 않는다.
  유실 대비는 새벽 백업(B 서버 rsync)이 담당.
- `hadoop.env` — HDFS 설정 (이미지가 `CORE-SITE.XML_*` 형식 환경변수를 설정 파일로 변환)
- `.env.example` — 환경별 값 (`KAFKA_BROKER`, `HDFS_UI_PORT`). `.env` 로 복사해 사용, 커밋 금지
- `create_topics.sh` — BE Kafka 에 토픽 생성 (자동 생성은 파티션 1 기본값으로 만들어버리므로 금지)
- `smoke_test.sh` — 배포 합격 판정 (HDFS 쓰기/읽기/복제 + Kafka 왕복)
- `airflow/Dockerfile` — Airflow + JDK + pyspark + 크롤러 의존성. Spark 는 별도 클러스터 없이
  DAG 태스크가 `spark-submit --master local[*]` 로 이 컨테이너 안에서 실행
- `postgres` — Airflow 메타DB (LocalExecutor 는 SQLite 미지원)

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
HDFS UI(9870)는 무인증이라 compose 에서 서버 내부 전용(127.0.0.1)으로 묶여 있다.

## 전 구간 검증

Airflow 웹 UI 에서 `spark_smoke` DAG 수동 트리거 → 성공이면 Airflow→Spark→HDFS 정상.
CLI 로는 `docker compose exec airflow airflow dags trigger spark_smoke`
