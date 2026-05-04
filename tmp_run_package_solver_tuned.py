from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / 'src'
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from vision_ai_recaptcha_solver.config import SolverConfig
from vision_ai_recaptcha_solver.solver import RecaptchaSolver


def check_tile_for_object(args):
    tile_index, tile_path, object_name, provider, model = args
    try:
        from visionai_local import visionai_contains_object
        decision = visionai_contains_object(tile_path, object_name)
        print(f"Tile {tile_index}: Does it contain '{object_name}'? VisionAI says: {str(decision).lower()}")
        return tile_index, decision
    except Exception as e:
        print(f"Error checking tile {tile_index}: {e}")
        return tile_index, False


def ask_instruction(image_path, provider, model):
    return ''


if __name__ == '__main__':
    config = SolverConfig(
        conf_threshold=0.7,
        detection_conf_threshold=0.6,
        square_max_confirmed_tiles=3,
        square_overselect_guard_threshold=5,
        square_medium_confidence_threshold=0.5,
    )
    result = RecaptchaSolver(config=config).solve_with_selenium_session(
        provider='visionai-local',
        model=None,
        max_rounds=5,
        screenshots_dir='screenshots-package-tuned',
        ask_recaptcha_instructions_with_provider=ask_instruction,
        check_tile_for_object=check_tile_for_object,
        debug=True,
        page_url='https://2captcha.com/demo/recaptcha-v2',
    )
    print(json.dumps(result, indent=2))
