#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/projects/private-captcha-solver
source .venv/bin/activate
exec python3 token_harvest/recaptchav2_server.py
