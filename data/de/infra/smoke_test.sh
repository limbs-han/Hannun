#!/usr/bin/env bash
# 스택 합격 판정 — HDFS 쓰기/읽기가 성공해야 PASS.
# KAFKA_BROKER 가 설정돼 있으면 원격 Kafka 왕복까지 판정한다 (미설정이면 HDFS만).
set -e
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")"
[ -f .env ] && source .env
NN=${NAMENODE_CONTAINER:-infra-namenode-1}
TOPIC=news.article.raw
MSG='{"article_id":"smoke","title":"smoke test"}'

echo "[1/3] HDFS: DataNode 1대 생존"
docker exec "$NN" hdfs dfsadmin -report 2>/dev/null | grep -q "Live datanodes (1)"

echo "[2/3] HDFS: 쓰기/읽기 왕복"
docker exec "$NN" sh -c "echo '$MSG' > /tmp/smoke.jsonl && hdfs dfs -mkdir -p /lake/_smoke && hdfs dfs -put -f /tmp/smoke.jsonl /lake/_smoke/"
docker exec "$NN" hdfs dfs -cat /lake/_smoke/smoke.jsonl | grep -q '"article_id":"smoke"'
docker exec "$NN" hdfs fsck /lake/_smoke/smoke.jsonl -files -blocks 2>/dev/null | grep -q "Live_repl=1"
docker exec "$NN" hdfs dfs -rm -r -skipTrash /lake/_smoke > /dev/null

if [ -n "$KAFKA_BROKER" ]; then
  echo "[3/3] Kafka: 프로듀스/컨슘 왕복 ($KAFKA_BROKER)"
  docker run --rm -i --network host apache/kafka:3.9.1 sh -c \
    "echo '$MSG' | /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server $KAFKA_BROKER --topic $TOPIC"
  docker run --rm --network host apache/kafka:3.9.1 \
    /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server "$KAFKA_BROKER" \
    --topic "$TOPIC" --from-beginning --timeout-ms 10000 2>/dev/null | grep -q '"article_id":"smoke"'
else
  echo "[3/3] Kafka: KAFKA_BROKER 미설정 — 건너뜀"
fi

echo "PASS — 스택 정상"
