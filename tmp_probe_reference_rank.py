from __future__ import annotations

import os
import sys
import time
from pathlib import Path

LOCAL_SRC = '/root/.openclaw/workspace/projects/private-captcha-solver/src'
if LOCAL_SRC not in sys.path:
    sys.path.insert(0, LOCAL_SRC)

from vision_ai_recaptcha_solver.browser.factory import create_replicator_session

OUT_DIR = Path('/root/.openclaw/workspace/projects/private-captcha-solver/screenshots/probe-3x3-live')
OUT_DIR.mkdir(parents=True, exist_ok=True)
GRID_PATH = OUT_DIR / 'grid_ref_probe.jpg'
TARGET_PATH = OUT_DIR / 'target_ref_probe.txt'

session = None
try:
    session = create_replicator_session(
        website_key='6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-',
        website_url='https://www.google.com/recaptcha/api2/demo',
        headless=True,
        download_dir='tmp/replicator-3x3-probe-ref',
        server_port=9943,
    )
    browser = session.browser
    tab = browser.latest_tab if hasattr(browser, 'latest_tab') else browser
    checkbox_frame = tab.get_frame(tab.eles('t:iframe')[0])
    checkbox_frame.ele('.recaptcha-checkbox-border', timeout=5).click()
    time.sleep(3)
    challenge_iframe = [f for f in tab.eles('t:iframe') if 'challenge' in ((f.attr('title') or '').lower()) or 'bframe' in ((f.attr('src') or '').lower())][0]
    frame = tab.get_frame(challenge_iframe)
    strong = frame.ele('tag:strong', timeout=2)
    target = (strong.text or '').strip().lower() if strong else ''
    table = frame.ele('xpath://table[contains(@class, "rc-imageselect-table")]', timeout=2)
    table.get_screenshot(path=str(GRID_PATH))
    TARGET_PATH.write_text(target, encoding='utf-8')
    print('GRID_PATH', GRID_PATH)
    print('TARGET', target)
finally:
    if session is not None:
        session.close()
