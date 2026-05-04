#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from selenium import webdriver

from recaptchav2_engine import solve_recaptcha_v2
from ai_utils import ask_recaptcha_instructions_with_provider
from main import check_tile_for_object


DEFAULT_DEMO_URL = 'https://2captcha.com/demo/recaptcha-v2'

HOST = os.getenv('RECAPTCHAV2_HOST', '127.0.0.1')
PORT = int(os.getenv('RECAPTCHAV2_PORT', '7862'))
DEBUG_DIR = Path(os.getenv('RECAPTCHAV2_DEBUG_DIR', Path(__file__).with_name('debug_v2')))
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PROXY = os.getenv('RECAPTCHAV2_PROXY', '').strip()
GEMINI_COMMAND = os.getenv('GEMINI_CLI_COMMAND', 'gemini')


def now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def build_chrome_options(proxy=None, user_agent=None):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-zygote')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-features=site-per-process,Translate,BackForwardCache,PaintHolding')
    chrome_options.add_argument('--js-flags=--max-old-space-size=256')
    chrome_options.add_argument('--remote-debugging-pipe')
    chrome_options.add_argument('--window-size=1366,768')
    selected_proxy = (proxy if proxy is not None else os.getenv('RECAPTCHAV2_PROXY', '')).strip()
    if selected_proxy:
        chrome_options.add_argument(f'--proxy-server={selected_proxy}')
    selected_user_agent = (user_agent or '').strip()
    if selected_user_agent:
        chrome_options.add_argument(f'--user-agent={selected_user_agent}')
    profile_dir = tempfile.mkdtemp(prefix='recaptchav2-chrome-', dir='/tmp')
    chrome_options.add_argument(f'--user-data-dir={profile_dir}')
    chrome_options.binary_location = os.getenv('CHROME_BINARY', '/usr/bin/google-chrome')
    return chrome_options, profile_dir


def parse_tile_indices(text, cols=3):
    text = (text or '').strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get('tiles') or payload.get('indices') or payload.get('answers') or []
        if isinstance(payload, list):
            values = [int(x) for x in payload]
        else:
            values = []
    except Exception:
        values = [int(x) for x in re.findall(r'\b(?:[1-9]|1[0-6])\b', text)]
    max_cell = 16 if int(cols) == 4 else 9
    deduped = []
    for value in values:
        if 1 <= value <= max_cell and value not in deduped:
            deduped.append(value)
    return deduped


def rank_grid_tiles_with_gemini(grid_path, object_name, cols):
    max_cell = 16 if int(cols) == 4 else 9
    prompt = (
        f"Analyze the CAPTCHA grid image at this local file path: {grid_path}\n"
        f"The grid has {cols} columns and cells numbered left-to-right, top-to-bottom from 1 to {max_cell}.\n"
        f"Return ONLY a JSON array of cell numbers that contain '{object_name}' or a recognizable part of it.\n"
        "If none match, return []. No markdown. No explanation."
    )
    try:
        proc = subprocess.run(
            [GEMINI_COMMAND, '-p', prompt],
            capture_output=True,
            text=True,
            timeout=int(os.getenv('RECAPTCHAV2_GEMINI_TIMEOUT', '180')),
        )
        if proc.returncode != 0:
            selected = []
        else:
            selected = parse_tile_indices(proc.stdout, cols=cols)
    except subprocess.TimeoutExpired:
        selected = []
    return [(cell, 1.0 if cell in selected else 0.0) for cell in range(1, max_cell + 1)]


def select_proxy(payload):
    if payload.get('noProxy') is True:
        return ''
    if 'proxy' in payload:
        return payload.get('proxy') or None
    return os.getenv('RECAPTCHAV2_PROXY', '').strip() or DEFAULT_PROXY or None


def make_driver(proxy=None, user_agent=None):
    chrome_options, profile_dir = build_chrome_options(proxy=proxy, user_agent=user_agent)
    driver = webdriver.Chrome(options=chrome_options)
    return driver, profile_dir


def preseed_cookies(driver, cookies, page_url):
    """Set Cloudflare/session cookies before the solver opens the protected page."""
    if not cookies:
        return 0
    try:
        driver.execute_cdp_cmd('Network.enable', {})
    except Exception:
        pass
    count = 0
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        name = cookie.get('name')
        value = cookie.get('value')
        if not name or value is None:
            continue
        payload = {
            'name': name,
            'value': value,
            'url': page_url or 'https://coinadster.com/',
            'path': cookie.get('path') or '/',
        }
        if cookie.get('domain'):
            payload['domain'] = cookie.get('domain')
        if cookie.get('secure') is not None:
            payload['secure'] = bool(cookie.get('secure'))
        if cookie.get('httpOnly') is not None:
            payload['httpOnly'] = bool(cookie.get('httpOnly'))
        try:
            driver.execute_cdp_cmd('Network.setCookie', payload)
            count += 1
        except Exception:
            try:
                driver.get(page_url or 'https://coinadster.com/')
                driver.add_cookie({k: v for k, v in payload.items() if k in ('name', 'value', 'path', 'domain', 'secure', 'httpOnly')})
                count += 1
            except Exception:
                pass
    return count


class Handler(BaseHTTPRequestHandler):
    server_version = 'PrivateRecaptchaV2/0.1.0'

    def _send(self, status, payload):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == '/':
            self._send(200, {
                'status': 'ok',
                'service': 'private-recaptchav2',
                'version': '0.1.0',
                'time': now_iso(),
            })
            return
        self._send(404, {'status': 'error', 'message': 'not found'})

    def do_POST(self):
        if self.path != '/recaptchav2':
            self._send(404, {'status': 'error', 'message': 'not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length) if length > 0 else b'{}'
            payload = json.loads(body.decode('utf-8'))
        except Exception as exc:
            self._send(400, {'status': 'error', 'message': f'invalid json: {exc}'})
            return

        driver = None
        profile_dir = None
        try:
            proxy = select_proxy(payload)
            user_agent = payload.get('userAgent') or payload.get('ua') or ''
            driver, profile_dir = make_driver(proxy=proxy, user_agent=user_agent)
            provider = payload.get('provider') or 'gemini-cli'
            model = payload.get('model')
            instruction_provider = payload.get('instructionProvider') or provider
            instruction_model = payload.get('instructionModel')
            max_rounds = int(payload.get('maxRounds') or 5)
            debug = payload.get('debug', True) is not False
            page_url = payload.get('pageUrl') or DEFAULT_DEMO_URL
            request_id = payload.get('requestId') or f"run_{int(datetime.utcnow().timestamp())}"
            screenshots_dir = str(DEBUG_DIR / request_id)
            os.makedirs(screenshots_dir, exist_ok=True)
            cookie_count = preseed_cookies(driver, payload.get('cookies') or [], page_url)

            def ask_instruction(image_path, _provider, _model):
                return ask_recaptcha_instructions_with_provider(image_path, instruction_provider, instruction_model)

            rank_grid_tiles = rank_grid_tiles_with_gemini if provider == 'gemini-cli-grid' else None

            result = solve_recaptcha_v2(
                driver=driver,
                provider=provider,
                model=model,
                max_rounds=max_rounds,
                screenshots_dir=screenshots_dir,
                ask_recaptcha_instructions_with_provider=ask_instruction,
                check_tile_for_object=check_tile_for_object,
                rank_grid_tiles=rank_grid_tiles,
                debug=debug,
                page_url=page_url,
                preJavaScript=payload.get('preJavaScript') or payload.get('pre_javascript'),
                preJavaScriptWait=payload.get('preJavaScriptWait') or payload.get('pre_javascript_wait'),
            )
            result['requestId'] = request_id
            result['pageUrl'] = page_url
            result['proxy'] = proxy or ''
            result['cookiePreseedCount'] = cookie_count
            result['userAgentPreseeded'] = bool(user_agent)
            result['time'] = now_iso()
            try:
                Path(screenshots_dir, 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            except Exception:
                pass
            self._send(200, result)
        except Exception as exc:
            self._send(500, {
                'status': 'error',
                'message': str(exc),
                'traceback': traceback.format_exc(),
                'time': now_iso(),
            })
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            if profile_dir:
                try:
                    shutil.rmtree(profile_dir, ignore_errors=True)
                except Exception:
                    pass


def serve():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(json.dumps({'event': 'recaptchav2_server_start', 'host': HOST, 'port': PORT, 'time': now_iso()}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    serve()
