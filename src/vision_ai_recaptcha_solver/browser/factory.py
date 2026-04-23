from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any

from vision_ai_recaptcha_solver.browser.session import BrowserSession


def create_selenium_session() -> BrowserSession:
    from selenium import webdriver

    chrome_profile_dir = tempfile.mkdtemp(prefix='private-captcha-solver-chrome-')
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-features=site-per-process,Translate,BackForwardCache,PaintHolding')
    chrome_options.add_argument('--js-flags=--max-old-space-size=256')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-zygote')
    chrome_options.add_argument('--remote-debugging-pipe')
    chrome_options.add_argument(f'--user-data-dir={chrome_profile_dir}')
    chrome_options.add_argument('--window-size=1366,768')
    chrome_options.binary_location = os.getenv('CHROME_BINARY', '/usr/bin/google-chrome')
    driver = webdriver.Chrome(options=chrome_options)
    session = BrowserSession(mode='selenium', browser=driver)
    session._chrome_profile_dir = chrome_profile_dir  # type: ignore[attr-defined]
    return session


def create_replicator_session(*, website_key: str, website_url: str, is_invisible: bool = False, action: str | None = None, is_enterprise: bool = False, api_domain: str = 'google.com', bypass_domain_check: bool = True, use_ssl: bool = True, cookies: list[dict[str, Any]] | None = None, user_agent: str | None = None, headless: bool = True, download_dir: str = 'tmp/visionai-local', server_port: int = 8443, proxy: str | None = None, browser_path: str | None = None, persist_html: bool = False) -> BrowserSession:
    from recaptcha_domain_replicator import RecaptchaDomainReplicator

    replicator = RecaptchaDomainReplicator(
        download_dir=download_dir,
        server_port=server_port,
        persist_html=persist_html,
        proxy=proxy,
        browser_path=browser_path,
    )
    browser, token_handle = replicator.replicate_captcha(
        website_key=website_key,
        website_url=website_url,
        is_invisible=is_invisible,
        action=action,
        is_enterprise=is_enterprise,
        api_domain=api_domain,
        bypass_domain_check=bypass_domain_check,
        use_ssl=use_ssl,
        cookies=cookies,
        user_agent=user_agent,
        headless=headless,
    )
    return BrowserSession(mode='replicator', browser=browser, token_handle=token_handle, replicator=replicator)


def cleanup_selenium_session(session: BrowserSession) -> None:
    chrome_profile_dir = getattr(session, '_chrome_profile_dir', None)
    session.close()
    if chrome_profile_dir:
        shutil.rmtree(chrome_profile_dir, ignore_errors=True)
