#!/usr/bin/env bash
# 토픽 생성 스크립트 — 재구축 시 이 파일만 다시 실행.
# Kafka 브로커는 BE 소유(B 서버)라 원격 주소를 .env 의 KAFKA_BROKER 로 받는다.
set -e
# Windows Git Bash가 /opt/... 를 윈도우 경로로 바꿔치기하는 것 방지 (리눅스에선 무해)
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")"
[ -f .env ] && source .env
: "${KAFKA_BROKER:?KAFKA_BROKER 가 비어 있음 — .env 를 확인하세요}"

kafka_cli() {
  docker run --rm --network host apache/kafka:3.9.1 \
    /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$KAFKA_BROKER" "$@"
}

create() {
  kafka_cli --create --if-not-exists --topic "$1" --partitions "$2" --replication-factor 1
}

create news.article.realtime.v1 3
# 이용 로그 토픽은 스프린트 4에 활성화
# create user.events.v1 3

kafka_cli --list
