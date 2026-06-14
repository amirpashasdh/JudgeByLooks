import os
import sys
import shutil
import cv2

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)


def _ensure_path():
    if STYLE_KEYWORDS_DIR not in sys.path:
        sys.path.insert(0, STYLE_KEYWORDS_DIR)


def run_analysis(image_path: str, session_id: str) -> dict:
    _ensure_path()

    # change to style-keywords dir so storage.py writes keywords.db there
    original_cwd = os.getcwd()
    os.chdir(STYLE_KEYWORDS_DIR)

    try:
        from storage import init_db, save_analysis
        from detector import PersonDetector
        from analyzer import StyleAnalyzer

        run_folder = os.path.join(STYLE_KEYWORDS_DIR, "Results", f"run_{session_id}")
        os.makedirs(run_folder, exist_ok=True)

        dest = os.path.join(run_folder, "input.jpg")
        shutil.copy2(image_path, dest)

        init_db()
        detector = PersonDetector()
        analyzer = StyleAnalyzer()

        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Could not read image: {image_path}")

        crops = detector.get_person_crops(frame)
        crop = max(crops, key=lambda c: c.shape[0] * c.shape[1]) if crops else frame

        import json
        result = analyzer.analyze(crop)
        if result:
            raw = json.dumps(result)
            scores = result
        else:
            from storage import KEYWORDS
            scores = {k: 0.0 for k in KEYWORDS}
            raw = json.dumps(scores)

        person_id = save_analysis(dest, raw, scores)

        return {
            "person_id": person_id,
            "keywords": scores,
            "run_folder": run_folder,
        }
    finally:
        os.chdir(original_cwd)
