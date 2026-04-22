#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/projects/private-captcha-solver
source .venv/bin/activate
export GEMINI_CLI_COMMAND=gemini
exec python main.py complicated_text --provider gemini-cli
