#!/usr/bin/env bash
# 一条命令跑完后端断言与前端静态守卫
set -u
cd "$(dirname "$0")/.."
echo "== pytest =="
.venv/bin/python -m pytest tests -q
py=$?
echo "== frontend static guard =="
node tests/frontend_guard.js
js=$?
if [ "$py" -ne 0 ] || [ "$js" -ne 0 ]; then
  exit 1
fi
echo "全部通过"
