#!/usr/bin/env bash
# 프론트(Vue SPA) 배포 스크립트. ~/news-platform/front/deploy 에서 실행(Jenkins가 이 스크립트를 호출).
#
# 흐름: Node 컨테이너로 빌드(호스트에 node 설치 불필요) -> 산출물(dist/)을
#      nginx가 서빙하는 고정 경로로 교체(rsync --delete로 이전 빌드 잔재까지 정리).
# 백엔드처럼 블루/그린이 필요 없음 - 정적 파일이라 교체 자체가 원자적이진 않지만
# rsync 한 번이 워낙 빨라서(수백 ms) 그 사이 요청이 섞일 확률이 낮고, 설령 섞여도
# 정적 파일 몇 개 버전 불일치 정도라 백엔드 blue/green만큼 엄격하게 다룰 이유가 없음.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONT_DIR="$(dirname "$DEPLOY_DIR")"
SERVE_DIR="/var/www/news-front"

echo "==> Node 컨테이너에서 빌드"
docker run --rm -v "$FRONT_DIR":/app -w /app node:20-alpine sh -c "npm ci && npm run build"

echo "==> 빌드 산출물(dist/)을 서빙 경로로 교체"
sudo mkdir -p "$SERVE_DIR"
sudo rsync -a --delete "$FRONT_DIR/dist/" "$SERVE_DIR/"

echo "==> 배포 완료"
