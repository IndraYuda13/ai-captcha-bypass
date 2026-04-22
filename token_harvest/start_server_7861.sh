#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/projects/private-captcha-solver/token_harvest
export PRIVATE_SOLVER_PORT=7861
exec node server.js
