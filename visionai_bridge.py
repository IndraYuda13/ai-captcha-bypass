#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import cv2

VISION_REPO = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver')
VISION_SRC = VISION_REPO / 'src'
if str(VISION_SRC) not in sys.path:
    sys.path.insert(0, str(VISION_SRC))

from vision_ai_recaptcha_solver.detector.yolo_detector import YOLODetector
from vision_ai_recaptcha_solver.types import CaptchaType


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Run VisionAIRecaptchaSolver local detector on an existing grid image.')
    p.add_argument('--image', required=True, help='Path to captcha grid image')
    p.add_argument('--target', required=True, help='Target keyword, e.g. bicycles, buses, crosswalks')
    p.add_argument('--captcha-type', choices=['selection_3x3', 'dynamic_3x3', 'square_4x4'], default='selection_3x3')
    p.add_argument('--model-path', default=str(VISION_REPO / 'src/vision_ai_recaptcha_solver/models/recaptcha_classification_57k.onnx'))
    p.add_argument('--detection-model-path', default='yolo12x.pt')
    p.add_argument('--conf-threshold', type=float, default=0.7)
    p.add_argument('--min-confidence-threshold', type=float, default=0.2)
    p.add_argument('--fourth-cell-threshold', type=float, default=0.7)
    p.add_argument('--detection-conf-threshold', type=float, default=0.6)
    p.add_argument('--verbose', action='store_true')
    return p


def main() -> int:
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s',
    )
    logger = logging.getLogger('visionai-bridge')

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f'image not found: {image_path}')

    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f'failed to read image: {image_path}')

    detector = YOLODetector(
        model_path=args.model_path,
        detection_model_path=args.detection_model_path,
        verbose=args.verbose,
        logger=logging.getLogger('vision_ai_recaptcha_solver'),
        conf_threshold=args.conf_threshold,
        fourth_cell_threshold=args.fourth_cell_threshold,
        detection_conf_threshold=args.detection_conf_threshold,
    )
    detector.ensure_warmup_complete(timeout=60)

    captcha_type = {
        'selection_3x3': CaptchaType.SELECTION_3X3,
        'dynamic_3x3': CaptchaType.DYNAMIC_3X3,
        'square_4x4': CaptchaType.SQUARE_4X4,
    }[args.captcha_type]

    if captcha_type == CaptchaType.SQUARE_4X4:
        target_class = detector.get_coco_target_class(args.target)
        if target_class is None:
            raise SystemExit(f'no COCO class mapping for target: {args.target}')
        answers = detector.detect_for_grid(image, target_class=target_class, grid_size=450)
        result = {
            'mode': 'detect_4x4',
            'target': args.target,
            'targetClass': target_class,
            'answers': answers,
        }
    else:
        target_class = detector.get_target_class(args.target)
        if target_class is None:
            raise SystemExit(f'no classification target mapping for target: {args.target}')
        confidences = detector.classify_tiles_with_confidence(image, grid_size=3, target_class=target_class)
        ranked = sorted(confidences, key=lambda x: x[1], reverse=True)
        answers = [cell for cell, _ in ranked[:3]]
        if len(ranked) >= 4 and ranked[3][1] >= args.fourth_cell_threshold:
            answers.append(ranked[3][0])
        result = {
            'mode': 'classify_3x3',
            'target': args.target,
            'targetClass': target_class,
            'ranked': [{'cell': cell, 'confidence': conf} for cell, conf in ranked],
            'answers': answers,
            'thresholds': {
                'confThreshold': args.conf_threshold,
                'minConfidenceThreshold': args.min_confidence_threshold,
                'fourthCellThreshold': args.fourth_cell_threshold,
            },
        }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
