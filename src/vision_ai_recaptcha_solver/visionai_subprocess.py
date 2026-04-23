from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

VISION_PYTHON = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/.venv/bin/python')
VISION_SRC = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/src')
VISION_SITE = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/.venv/lib/python3.12/site-packages')
RUNNER = Path('/root/.openclaw/workspace/projects/private-captcha-solver/tmp_visionai_rank_runner.py')


def visionai_rank_grid_tiles_subprocess(grid_path: str, object_name: str, grid_size: int) -> list[tuple[int, float]]:
    cmd = [
        str(VISION_PYTHON),
        str(RUNNER),
        str(grid_path),
        str(object_name),
        str(grid_size),
    ]
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{VISION_SRC}:{VISION_SITE}"
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    stdout = (result.stdout or '').strip()
    stderr = (result.stderr or '').strip()
    if result.returncode != 0:
        raise RuntimeError(f'visionai subprocess failed rc={result.returncode} stdout={stdout} stderr={stderr}')
    payload = json.loads(stdout)
    if not payload.get('ok'):
        raise RuntimeError(payload.get('error') or f'visionai subprocess runner failed stderr={stderr}')
    return [(int(cell), float(score)) for cell, score in payload['ranked']]
