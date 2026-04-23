from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from threading import Lock

VISION_REPO = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver')
VISION_SRC = VISION_REPO / 'src'
if str(VISION_SRC) not in sys.path:
    sys.path.insert(0, str(VISION_SRC))

VISION_VENV = VISION_REPO / '.venv/lib/python3.12/site-packages'
if str(VISION_VENV) not in sys.path:
    sys.path.insert(0, str(VISION_VENV))

import cv2
from vision_ai_recaptcha_solver.detector.yolo_detector import YOLODetector
from vision_ai_recaptcha_solver.types import CaptchaType, CLASS_NAMES

_MODEL_PATH = VISION_REPO / 'src/vision_ai_recaptcha_solver/models/recaptcha_classification_57k.onnx'
_DETECTION_MODEL_PATH = VISION_REPO / 'yolo12x.pt'
_DETECTOR = None
_DETECTOR_LOCK = Lock()


def _get_detector() -> YOLODetector:
    global _DETECTOR
    with _DETECTOR_LOCK:
        if _DETECTOR is None:
            _DETECTOR = YOLODetector(
                model_path=_MODEL_PATH,
                detection_model_path=str(_DETECTION_MODEL_PATH),
                verbose=False,
                logger=logging.getLogger('vision_ai_recaptcha_solver'),
                conf_threshold=0.7,
                fourth_cell_threshold=0.7,
                detection_conf_threshold=0.6,
            )
            _DETECTOR.ensure_warmup_complete(timeout=60)
        return _DETECTOR


def visionai_contains_object(image_path: str, object_name: str) -> bool:
    detector = _get_detector()
    target_class = detector.get_target_class(object_name)
    if target_class is None:
        return False
    image = cv2.imread(str(image_path))
    if image is None:
        return False
    confidence = detector.get_target_confidence(image, target_class)
    return confidence >= detector.conf_threshold


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
    detector = _get_detector()
    image = cv2.imread(str(grid_path))
    if image is None:
        raise RuntimeError(f'failed to read grid image: {grid_path}')

    if grid_size == 4:
        target_class = detector.get_coco_target_class(object_name)
        if target_class is not None:
            answers = detector.detect_for_grid(
                image,
                target_class=target_class,
                grid_size=450,
                conf_threshold=max(detector.detection_conf_threshold, 0.72),
            )
            if answers:
                rows = {}
                cols = {}
                for cell in answers:
                    r = (cell - 1) // 4
                    c = (cell - 1) % 4
                    rows[r] = rows.get(r, 0) + 1
                    cols[c] = cols.get(c, 0) + 1

                dense = []
                edge = []
                for cell in answers:
                    r = (cell - 1) // 4
                    c = (cell - 1) % 4
                    score = rows.get(r, 0) + cols.get(c, 0)
                    if score >= 4:
                        dense.append(cell)
                    else:
                        edge.append(cell)

                def is_adjacent(a, b):
                    ar, ac = (a - 1) // 4, (a - 1) % 4
                    br, bc = (b - 1) // 4, (b - 1) % 4
                    return abs(ar - br) <= 1 and abs(ac - bc) <= 1

                if dense:
                    answers = sorted(set(dense))
                    for cand in edge:
                        if any(is_adjacent(cand, keep) for keep in answers):
                            r = (cand - 1) // 4
                            c = (cand - 1) % 4
                            if rows.get(r, 0) >= 1 and cols.get(c, 0) >= 1:
                                answers.append(cand)
                    answers = sorted(set(answers))

                if len(answers) > 8:
                    answers = [cell for cell in answers if rows.get((cell - 1) // 4, 0) >= 2]
                    answers = sorted(set(answers))
            return [(cell, 1.0 if cell in answers else 0.0) for cell in range(1, 17)]

        target_class = detector.get_target_class(object_name)
        if target_class is None:
            raise RuntimeError(f'no classification mapping for target: {object_name}')
        ranked = detector.classify_tiles_with_confidence(image, grid_size=4, target_class=target_class)
        return ranked

    target_class = detector.get_target_class(object_name)
    if target_class is None:
        raise RuntimeError(f'no classification target mapping for target: {object_name}')
    return detector.classify_tiles_with_confidence(image, grid_size=grid_size, target_class=target_class)
