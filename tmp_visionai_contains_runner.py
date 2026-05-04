from __future__ import annotations

import json
import sys
from pathlib import Path

VISION_REPO = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver')
VISION_SRC = VISION_REPO / 'src'
VISION_SITE = VISION_REPO / '.venv/lib/python3.12/site-packages'
for p in (str(VISION_SRC), str(VISION_SITE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import cv2
from vision_ai_recaptcha_solver.detector.yolo_detector import YOLODetector

MODEL_PATH = VISION_REPO / 'src/vision_ai_recaptcha_solver/models/recaptcha_classification_57k.onnx'
DETECTION_MODEL_PATH = VISION_REPO / 'yolo12x.pt'


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({'ok': False, 'error': 'usage: contains_runner <image_path> <object_name>'}))
        return 1

    image_path = sys.argv[1]
    object_name = sys.argv[2]
    detector = YOLODetector(
        model_path=MODEL_PATH,
        detection_model_path=str(DETECTION_MODEL_PATH),
        verbose=False,
        conf_threshold=0.7,
        fourth_cell_threshold=0.7,
        detection_conf_threshold=0.6,
    )
    detector.ensure_warmup_complete(timeout=60)
    target_class = detector.get_target_class(object_name)
    if target_class is None:
        print(json.dumps({'ok': True, 'contains': False, 'reason': 'target_class_missing'}))
        return 0
    image = cv2.imread(str(image_path))
    if image is None:
        print(json.dumps({'ok': False, 'error': 'image_read_failed'}))
        return 1
    confidence = float(detector.get_target_confidence(image, target_class))
    print(json.dumps({'ok': True, 'contains': confidence >= detector.conf_threshold, 'confidence': confidence}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
