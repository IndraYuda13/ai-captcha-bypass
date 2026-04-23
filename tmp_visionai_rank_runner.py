from __future__ import annotations

import json
import sys
from pathlib import Path

from vision_ai_recaptcha_solver.detector.yolo_detector import YOLODetector
import cv2

MODEL_PATH = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/src/vision_ai_recaptcha_solver/models/recaptcha_classification_57k.onnx')
DETECTION_MODEL_PATH = '/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/yolo12x.pt'


def main() -> int:
    if len(sys.argv) != 4:
        print(json.dumps({'ok': False, 'error': 'usage: rank_runner.py <grid_path> <target> <grid_size>'}))
        return 2

    grid_path = Path(sys.argv[1])
    target = sys.argv[2].strip().lower()
    grid_size = int(sys.argv[3])

    detector = YOLODetector(
        model_path=MODEL_PATH,
        detection_model_path=DETECTION_MODEL_PATH,
        verbose=False,
        conf_threshold=0.7,
        fourth_cell_threshold=0.7,
        detection_conf_threshold=0.6,
    )
    detector.ensure_warmup_complete(timeout=60)

    image = cv2.imread(str(grid_path))
    if image is None:
        print(json.dumps({'ok': False, 'error': f'failed to read {grid_path}'}))
        return 1

    if grid_size == 4:
        target_class = detector.get_coco_target_class(target)
        if target_class is not None:
            answers = detector.detect_for_grid(
                image,
                target_class=target_class,
                grid_size=450,
                conf_threshold=detector.detection_conf_threshold,
            )
            ranked = [[cell, 1.0 if cell in answers else 0.0] for cell in range(1, 17)]
            print(json.dumps({'ok': True, 'ranked': ranked}))
            return 0

    target_class = detector.get_target_class(target)
    if target_class is None:
        print(json.dumps({'ok': False, 'error': f'no target class for {target}'}))
        return 1

    ranked = detector.classify_tiles_with_confidence(image, grid_size=grid_size, target_class=target_class)
    print(json.dumps({'ok': True, 'ranked': ranked}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
