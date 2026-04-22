# Relay recovery notes

## 2026-04-22

Goal:
- make the private solver custom backend usable by restoring codex-slot-relay to current main slot auth snapshots

Observed root cause before recovery:
- private solver -> custom backend -> relay path worked through auth and request routing
- relay failed upstream with `refresh_token_reused`
- this indicates stale relay-local slot auth, not a broken solver adapter

Evidence:
- relay runtime had old slot state under `/root/codex-slot-relay-runtime`
- main slot store under `/root/.openclaw/agents/main/agent/codex-slots/slots.json` shows fresher saved snapshots dated 2026-04-21 for multiple active accounts

Chosen recovery lane:
- use `relay.py sync-slots` to refresh relay-managed slot auth from the main slot store before attempting manual re-login

Why this lane:
- minimal-diff
- lower risk than direct manual re-login across multiple slots
- preserves relay structure while replacing stale auth artifacts with fresher current slot snapshots

After sync, re-test order:
1. relay health
2. private solver custom backend smoke test
3. Coinadster resume
