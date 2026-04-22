#!/usr/bin/env bash
set -euo pipefail
exec python3 /root/.openclaw/workspace/extract-candidates/codex-slot-relay_public_candidate/relay.py --runtime-root /root/codex-slot-relay-runtime --profile codex-slot-relay serve
