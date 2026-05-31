#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# CARLA 연결 확인 파라미터
# 필요한 값은 이 블록만 수정해서 사용한다.
# ============================================================

CARLA_HOST=127.0.0.1
CARLA_PORT=2000
CARLA_TIMEOUT=5.0
CARLA_CROSSOVER_BOTTLE=carla-rgb64

# 다른 위치의 CrossOver app을 쓰려면 아래 주석을 해제해서 직접 지정한다.
# export CARLA_CROSSOVER_APP="/Applications/CrossOver.app"

# ============================================================
# 여기 아래는 보통 수정하지 않는다.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "Checking CARLA connection..."
echo "HOST    : $CARLA_HOST"
echo "PORT    : $CARLA_PORT"
echo "TIMEOUT : $CARLA_TIMEOUT"
echo "BOTTLE  : $CARLA_CROSSOVER_BOTTLE"
echo

CARLA_HOST="$CARLA_HOST" CARLA_PORT="$CARLA_PORT" CARLA_TIMEOUT="$CARLA_TIMEOUT" \
CARLA_CROSSOVER_BOTTLE="$CARLA_CROSSOVER_BOTTLE" \
  "$REPO_ROOT/scripts/check_carla_crossover_connection.sh"
