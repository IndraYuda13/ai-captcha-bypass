#!/usr/bin/env python3
"""Run the DannyLuna VisionAIRecaptchaSolver core for one request.

This helper is intentionally small and JSON-in/JSON-out so the legacy
`recaptchav2_server.py` API can stay stable while the heavy YOLO runtime lives
in a separate venv, normally `/mnt/visionai-ref-runtime/venv`.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


def patch_chrome_flags() -> None:
    """Patch recaptcha-domain-replicator for root/headless Linux containers."""
    try:
        import recaptcha_domain_replicator.browser_config as browser_config
        import recaptcha_domain_replicator.constants as constants
    except Exception:
        return
    for arg in ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"):
        if arg not in constants.CHROMIUM_ARGUMENTS:
            constants.CHROMIUM_ARGUMENTS = constants.CHROMIUM_ARGUMENTS + (arg,)
        if arg not in browser_config.CHROMIUM_ARGUMENTS:
            browser_config.CHROMIUM_ARGUMENTS = browser_config.CHROMIUM_ARGUMENTS + (arg,)


def solve(payload: dict[str, Any]) -> dict[str, Any]:
    patch_chrome_flags()
    from vision_ai_recaptcha_solver import RecaptchaSolver, SolverConfig

    request_id = payload.get("requestId") or "run"
    debug_dir = Path(payload.get("debugDir") or "/mnt/visionai-ref-runtime/debug")
    download_dir = Path(payload.get("downloadDir") or "/mnt/visionai-ref-runtime/tmp") / str(request_id)
    debug_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)

    site_key = payload.get("siteKey") or payload.get("websiteKey") or payload.get("website_key")
    page_url = payload.get("pageUrl") or payload.get("websiteUrl") or payload.get("website_url")
    if not site_key:
        raise ValueError("siteKey is required")
    if not page_url:
        raise ValueError("pageUrl is required")

    config = SolverConfig(
        download_dir=download_dir,
        server_port=int(payload.get("serverPort") or os.getenv("RECAPTCHAV2_REPLICATOR_PORT", "8462")),
        proxy=(payload.get("proxy") or None),
        browser_path=os.getenv("CHROME_BINARY", payload.get("browserPath") or "/usr/bin/google-chrome"),
        headless=payload.get("headless", True) is not False,
        timeout=float(payload.get("timeout") or os.getenv("RECAPTCHAV2_TOKEN_TIMEOUT", "700")),
        max_attempts=int(payload.get("maxRounds") or payload.get("maxAttempts") or 8),
        persist_html=payload.get("persistHtml", True) is not False,
        cleanup_tmp_on_close=payload.get("cleanupTmpOnClose", False) is not False,
        log_level=str(payload.get("logLevel") or os.getenv("RECAPTCHAV2_LOG_LEVEL", "WARNING")),
    )

    with RecaptchaSolver(config) as solver:
        result = solver.solve(
            website_key=str(site_key),
            website_url=str(page_url),
            is_invisible=bool(payload.get("isInvisible", False)),
            action=payload.get("action"),
            is_enterprise=bool(payload.get("isEnterprise", False)),
            api_domain=str(payload.get("apiDomain") or "google.com"),
            bypass_domain_check=payload.get("bypassDomainCheck", True) is not False,
            use_ssl=payload.get("useSsl", False) is not False,
            cookies=payload.get("cookies") or [],
            user_agent=payload.get("userAgent") or payload.get("ua") or None,
        )

    return {
        "status": "success" if result.token else "error",
        "verified": bool(result.token),
        "token": result.token or "",
        "stage": "verified" if result.token else "no_token",
        "message": "solved" if result.token else "no token returned",
        "captchaType": str(result.captcha_type),
        "attempts": result.attempts,
        "timeTaken": result.time_taken,
        "cookies": result.cookies,
        "requestId": request_id,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = solve(payload)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("verified") else 2
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "verified": False,
            "token": "",
            "stage": "exception",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
