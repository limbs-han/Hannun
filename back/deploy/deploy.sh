#!/usr/bin/env bash
# 블루그린 배포 스크립트. ~/news-platform/deploy 에서 실행(젠킨스도 나중에 이 스크립트를 그대로 호출).
#
# 흐름: 현재 비활성 색상에 새 이미지로 컨테이너 기동 -> 헬스체크 통과할 때까지 대기 ->
#      nginx upstream을 그 색상으로 스위치(reload, 끊김 없음) -> 예전 색상은 우아하게 종료(SIGTERM, 처리 중 요청 마무리)
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.app.yml"
STATE_FILE="$DEPLOY_DIR/.active_color"
UPSTREAM_CONF="/etc/nginx/conf.d/news-app-upstream.conf"
HEALTH_TIMEOUT_SEC=90
HEALTH_INTERVAL_SEC=3

declare -A PORT1=( [blue]=8080 [green]=8082 )
declare -A PORT2=( [blue]=8081 [green]=8083 )

active="blue"
if [[ -f "$STATE_FILE" ]]; then
    active="$(cat "$STATE_FILE")"
fi
if [[ "$active" == "blue" ]]; then
    target="green"
else
    target="blue"
fi

echo "==> 현재 활성 색상: $active, 이번 배포 대상: $target"

echo "==> [$target] 이미지 빌드 + 컨테이너 기동"
docker compose -f "$COMPOSE_FILE" up -d --build "app-${target}-1" "app-${target}-2"

echo "==> [$target] 헬스체크 대기 (최대 ${HEALTH_TIMEOUT_SEC}s)"
t1=${PORT1[$target]}
t2=${PORT2[$target]}
elapsed=0
while true; do
    ok1=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${t1}/actuator/health" || echo "000")
    ok2=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${t2}/actuator/health" || echo "000")
    if [[ "$ok1" == "200" && "$ok2" == "200" ]]; then
        echo "==> [$target] 헬스체크 통과 (${t1}:${ok1}, ${t2}:${ok2})"
        break
    fi
    if (( elapsed >= HEALTH_TIMEOUT_SEC )); then
        echo "!! [$target] 헬스체크 실패 - ${HEALTH_TIMEOUT_SEC}s 안에 UP 안 됨 (${t1}:${ok1}, ${t2}:${ok2})"
        echo "!! 배포 중단, 기존 활성 색상($active)은 그대로 유지됨. 실패한 [$target] 컨테이너 정리."
        docker compose -f "$COMPOSE_FILE" stop "app-${target}-1" "app-${target}-2"
        exit 1
    fi
    sleep "$HEALTH_INTERVAL_SEC"
    elapsed=$(( elapsed + HEALTH_INTERVAL_SEC ))
done

echo "==> nginx upstream을 [$target] 으로 전환"
cat > /tmp/news-app-upstream.conf << EOF
upstream news_app {
    server 127.0.0.1:${t1};
    server 127.0.0.1:${t2};
}
EOF
sudo cp /tmp/news-app-upstream.conf "$UPSTREAM_CONF"
sudo nginx -t
sudo systemctl reload nginx
echo "==> nginx 전환 완료 (트래픽 끊김 없음 - reload는 기존 연결을 안 끊고 새 연결부터 전환)"

echo "$target" > "$STATE_FILE"

echo "==> [$active] 우아한 종료 (SIGTERM, 처리 중이던 요청 마무리 후 종료)"
docker compose -f "$COMPOSE_FILE" stop "app-${active}-1" "app-${active}-2"

echo "==> 배포 완료. 활성 색상: $target"
