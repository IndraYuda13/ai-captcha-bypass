# Private solver usage

## Working backend right now

### Gemini CLI

Smoke-tested on 2026-04-22.

```bash
cd /root/.openclaw/workspace/projects/private-captcha-solver
source .venv/bin/activate
export GEMINI_CLI_COMMAND=gemini
python main.py text --provider gemini-cli
```

## Notes

- `gemini-cli` is the currently proven backend for the private solver stack in this environment.
- `custom` backend architecture is wired, but the current codex-slot-relay `codex-direct` upstream path is outdated and still needs a separate relay-side fix before it becomes usable.
- `codex` backend exists in code, but has not yet been smoke-tested live in this cycle.

## Next intended use

- Resume Coinadster with a solver-backed lane using the private solver stack and `gemini-cli` as the active backend.
