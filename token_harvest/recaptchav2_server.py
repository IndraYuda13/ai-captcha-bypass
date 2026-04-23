#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
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


def now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def make_driver():
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
    profile_dir = tempfile.mkdtemp(prefix='recaptchav2-chrome-', dir='/tmp')
    chrome_options.add_argument(f'--user-data-dir={profile_dir}')
    chrome_options.binary_location = os.getenv('CHROME_BINARY', '/usr/bin/google-chrome')
    driver = webdriver.Chrome(options=chrome_options)
    return driver, profile_dir


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
            driver, profile_dir = make_driver()
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

            def ask_instruction(image_path, _provider, _model):
                return ask_recaptcha_instructions_with_provider(image_path, instruction_provider, instruction_model)

            result = solve_recaptcha_v2(
                driver=driver,
                provider=provider,
                model=model,
                max_rounds=max_rounds,
                screenshots_dir=screenshots_dir,
                ask_recaptcha_instructions_with_provider=ask_instruction,
                check_tile_for_object=check_tile_for_object,
                debug=debug,
                page_url=page_url,
            )
            result['requestId'] = request_id
            result['pageUrl'] = page_url
            result['time'] = now_iso()
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
