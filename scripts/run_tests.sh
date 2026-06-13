#!/usr/bin/env bash
# 仅跑测试 (假定已 setup)。用法: bash scripts/run_tests.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
export DATABASE_URL="${DATABASE_URL:-sqlite:///./srs_test.db}"
export SECRET_KEY="${SECRET_KEY:-dev_secret_change_me}"
rm -f srs_test.db
pytest -q
