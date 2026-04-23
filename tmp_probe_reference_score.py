from __future__ import annotations

from pathlib import Path

from vision_ai_recaptcha_solver.detector.yolo_detector import YOLODetector

GRID_PATH = Path('/root/.openclaw/workspace/projects/private-captcha-solver/screenshots/probe-3x3-live/grid_ref_probe.jpg')
TARGET = Path('/root/.openclaw/workspace/projects/private-captcha-solver/screenshots/probe-3x3-live/target_ref_probe.txt').read_text(encoding='utf-8').strip().lower()
MODEL_PATH = Path('/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/src/vision_ai_recaptcha_solver/models/recaptcha_classification_57k.onnx')
DETECTION_MODEL_PATH = '/root/.openclaw/workspace/tmp-gh/VisionAIRecaptchaSolver/yolo12x.pt'


def main():
    detector = YOLODetector(
        model_path=MODEL_PATH,
        detection_model_path=DETECTION_MODEL_PATH,
        verbose=False,
        conf_threshold=0.7,
        fourth_cell_threshold=0.7,
        detection_conf_threshold=0.6,
    )
    detector.ensure_warmup_complete(timeout=60)
    import cv2
    image = cv2.imread(str(GRID_PATH))
    if image is None:
        raise RuntimeError(f'failed to read {GRID_PATH}')
    target_class = detector.get_target_class(TARGET)
    print('TARGET', TARGET)
    print('TARGET_CLASS', target_class)
    ranked = detector.classify_tiles_with_confidence(image, grid_size=3, target_class=target_class)
    ranked_sorted = sorted(ranked, key=lambda x: x[1], reverse=True)
    print('RANKED', ranked)
    print('TOP3', ranked_sorted[:3])
    if len(ranked_sorted) >= 4:
        print('TOP4', ranked_sorted[:4])


if __name__ == '__main__':
    main()
