import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'token_harvest'))
sys.path.insert(0, str(ROOT))

import recaptchav2_server


class RecaptchaV2ServerConfigTests(unittest.TestCase):
    def test_chrome_options_include_proxy_from_environment(self):
        with patch.dict(os.environ, {'RECAPTCHAV2_PROXY': 'http://127.0.0.1:31001'}, clear=False):
            options, profile_dir = recaptchav2_server.build_chrome_options()
        try:
            self.assertIn('--proxy-server=http://127.0.0.1:31001', options.arguments)
        finally:
            if profile_dir:
                Path(profile_dir).rmdir()

    def test_payload_proxy_overrides_default_proxy(self):
        with patch.dict(os.environ, {'RECAPTCHAV2_PROXY': 'http://127.0.0.1:31001'}, clear=False):
            options, profile_dir = recaptchav2_server.build_chrome_options(proxy='http://127.0.0.1:33100')
        try:
            self.assertIn('--proxy-server=http://127.0.0.1:33100', options.arguments)
            self.assertNotIn('--proxy-server=http://127.0.0.1:31001', options.arguments)
        finally:
            if profile_dir:
                Path(profile_dir).rmdir()


if __name__ == '__main__':
    unittest.main()

class RecaptchaV2GeminiGridTests(unittest.TestCase):
    def test_parse_gemini_tile_indices_handles_json_and_plain_text(self):
        self.assertEqual(recaptchav2_server.parse_tile_indices('[1, 3, 9]', cols=3), [1, 3, 9])
        self.assertEqual(recaptchav2_server.parse_tile_indices('tiles: 2, 5 and 6', cols=3), [2, 5, 6])

class RecaptchaV2ProxySelectionTests(unittest.TestCase):
    def test_select_proxy_can_disable_environment_default(self):
        with patch.dict(os.environ, {'RECAPTCHAV2_PROXY': 'http://127.0.0.1:31001'}, clear=False):
            self.assertEqual(recaptchav2_server.select_proxy({'noProxy': True}), '')
            self.assertEqual(recaptchav2_server.select_proxy({'proxy': 'http://127.0.0.1:31002'}), 'http://127.0.0.1:31002')
