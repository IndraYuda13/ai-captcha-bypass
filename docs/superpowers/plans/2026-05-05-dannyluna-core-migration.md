# DannyLuna Core Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unstable local reCAPTCHA v2 solving path with the proven DannyLuna VisionAIRecaptchaSolver core while preserving our `/recaptchav2` service API for Coinadster and future scripts.

**Architecture:** The `vision_ai_recaptcha_solver` package will be reset to the DannyLuna reference implementation, with a small runtime patch for container-safe Chrome flags. The local `token_harvest/recaptchav2_server.py` remains as our stable HTTP adapter and uses the DannyLuna `RecaptchaSolver` as the default backend. Heavy runtime dependencies and YOLO model live under `/mnt/visionai-ref-runtime` when root disk is tight.

**Tech Stack:** Python 3.12, recaptcha-domain-replicator, DrissionPage, ultralytics/YOLO, OpenCV, requests, FlareSolverr helper for Coinadster Cloudflare/session preflight.

---

### Task 1: Reset solver package to DannyLuna official core

**Files:**
- Replace: `src/vision_ai_recaptcha_solver/`
- Modify: `requirements.txt`

- [ ] Copy `/root/.openclaw/workspace/refs/VisionAIRecaptchaSolver/src/vision_ai_recaptcha_solver` into `projects/private-captcha-solver/src/vision_ai_recaptcha_solver`.
- [ ] Add official dependencies to `requirements.txt`: `recaptcha-domain-replicator>=1.0.6`, `ultralytics>=8.3`, `opencv-python>=4.8.0`, `numpy>=1.24.0`, `aiohttp>=3.9.0`, `click>=8.1.0`, `tenacity>=8.2.0`.
- [ ] Patch `browser/factory.py` to add Chrome flags `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu` before creating the replicator session.
- [ ] Verify import with `/mnt/visionai-ref-runtime/venv/bin/python -c "from vision_ai_recaptcha_solver import RecaptchaSolver"`.

### Task 2: Make `/recaptchav2` default to DannyLuna backend

**Files:**
- Modify: `token_harvest/recaptchav2_server.py`

- [ ] Keep endpoint shape: POST JSON with `pageUrl`, `siteKey`, `proxy`, `userAgent`, `cookies`, `maxRounds`.
- [ ] Default backend to `official`/DannyLuna.
- [ ] Keep legacy Selenium/Gemini path only when `backend=legacy`.
- [ ] Return stable JSON: `status`, `verified`, `token`, `stage`, `message`, `captchaType`, `attempts`, `timeTaken`, `cookies`, `requestId`.
- [ ] Persist `result.json` in debug dir for every attempt.

### Task 3: Update Coinadster helper to use official backend

**Files:**
- Modify: `/root/.openclaw/workspace/projects/coinadster-automation/src/coinadster_automation/recaptcha_solver.py`
- Modify: `/root/.openclaw/workspace/projects/coinadster-automation/src/coinadster_automation/cli.py`

- [ ] Send `backend=official` and `useReplicator=true` to `/recaptchav2`.
- [ ] Add timeout/retry handling for unsupported YOLO classes or long-running solver attempts.
- [ ] Keep token single-use discipline: generate fresh token immediately before login submit.

### Task 4: Verify and push

**Files:**
- Update: `artifacts/active/execution-notes.md`
- Update: `artifacts/active/parent-checklist.md`

- [ ] Run unit tests in `private-captcha-solver`.
- [ ] Run Coinadster preflight.
- [ ] Run one official token solve and login probe.
- [ ] Commit and push `private-captcha-solver` to `boskuu/main`.
- [ ] Commit and push `coinadster-automation` to `origin/master`.
