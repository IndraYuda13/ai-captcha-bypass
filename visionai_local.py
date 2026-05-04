from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

CLASS_NAMES = [
    {'bicycle': ['bicycle', 'bicycles']},
    {'boat': ['boat', 'boats']},
    {'bridge': ['bridge', 'bridges']},
    {'bus': ['bus', 'buses']},
    {'car': ['car', 'cars']},
    {'chimney': ['chimney', 'chimneys']},
    {'crosswalk': ['crosswalk', 'crosswalks']},
    {'fire_hydrant': ['fire hydrant', 'fire hydrants']},
    {'motorcycle': ['motorcycle', 'motorcycles']},
    {'palm_tree': ['palm tree', 'palm trees']},
    {'stair': ['stair', 'stairs']},
    {'taxi': ['taxi', 'taxis']},
    {'traffic_light': ['traffic light', 'traffic lights']},
]

VISION_REPO = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver')
VISION_SRC = VISION_REPO / 'src'
VISION_SITE = VISION_REPO / '.venv/lib/python3.12/site-packages'


def visionai_contains_object(image_path: str, object_name: str) -> bool:
    runner = Path('/root/.openclaw/workspace/projects/private-captcha-solver/tmp_visionai_contains_runner.py')
    cmd = [
        str(VISION_REPO / '.venv/bin/python'),
        str(runner),
        str(image_path),
        str(object_name),
    ]
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{VISION_SRC}:{VISION_SITE}"
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        stderr = (result.stderr or '').strip()
        stdout = (result.stdout or '').strip()
        raise RuntimeError(f'visionai contains runner failed rc={result.returncode} stdout={stdout[:300]} stderr={stderr[:300]}')
    payload = json.loads((result.stdout or '').strip())
    if not payload.get('ok'):
        raise RuntimeError(payload.get('error') or 'visionai contains runner failed')
    return bool(payload.get('contains'))


def visionai_extract_instruction_object(image_path: str) -> str:
    text = Path(image_path).read_bytes()
    text_guess = ''
    try:
        text_guess = text.decode('utf-8', errors='ignore').lower()
    except Exception:
        text_guess = ''

    for entry in CLASS_NAMES:
        canonical, aliases = next(iter(entry.items()))
        for alias in aliases:
            alias_lower = alias.lower()
            if alias_lower and alias_lower in text_guess:
                return canonical

    stem = Path(image_path).stem.lower()
    tokens = re.findall(r'[a-z]+', stem)
    for token in tokens:
        for entry in CLASS_NAMES:
            canonical, aliases = next(iter(entry.items()))
            alias_set = {a.lower() for a in aliases}
            if token in alias_set or token == canonical.lower():
                return canonical

    raise RuntimeError('visionai local instruction extraction is not implemented for screenshot OCR-like reading yet')


def visionai_rank_grid_tiles(grid_path: str, object_name: str, grid_size: int) -> list[tuple[int, float]]:
    runner = Path('/root/.openclaw/workspace/projects/private-captcha-solver/tmp_visionai_rank_runner.py')
    cmd = [
        str(VISION_REPO / '.venv/bin/python'),
        str(runner),
        str(grid_path),
        str(object_name),
        str(grid_size),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads((result.stdout or '').strip())
    if not payload.get('ok'):
        raise RuntimeError(payload.get('error') or 'visionai rank runner failed')
    return [(int(cell), float(score)) for cell, score in payload['ranked']]
