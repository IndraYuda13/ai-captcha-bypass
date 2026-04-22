#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/projects/private-captcha-solver
source .venv/bin/activate
export GEMINI_CLI_COMMAND=gemini
exec python main.py audio --provider gemini-cli --file files/audio.mp3
