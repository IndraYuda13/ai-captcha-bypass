#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/projects/private-captcha-solver
source .venv/bin/activate
export RECAPTCHAV2_PORT=7862
exec python token_harvest/recaptchav2_server.py
