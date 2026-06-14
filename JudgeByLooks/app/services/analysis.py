import os
import sys
import shutil
import cv2

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)


_detector_instance = None

def _get_detector():
    global _detector_instance
    if _detector_instance is None:
        from detector import PersonDetector
        _detector_instance = PersonDetector()
    return _detector_instance

def _ensure_path():
    if STYLE_KEYWORDS_DIR not in sys.path:
        sys.path.insert(0, STYLE_KEYWORDS_DIR)


def run_analysis(image_path: str, session_id: str, taxonomy_mode: str = "both") -> dict:
    """
    Run full stylist-brief analysis on image_path.

    Returns:
        person_id   — row id in keywords.db
        brief       — full stylist brief dict (current_outfit, style_scores, coloring,
                      context, price_tier, overall_confidence, low_confidence_fallback,
                      recommendations)
        keywords    — style_scores.keywords dict (for backward compat / upload response)
        run_folder  — path where input.jpg was saved
    """
    _ensure_path()

    original_cwd = os.getcwd()
    os.chdir(STYLE_KEYWORDS_DIR)

    try:
        import json
        from storage import init_db, save_analysis, KEYWORDS
        from analyzer import StyleAnalyzer

        run_folder = os.path.join(STYLE_KEYWORDS_DIR, "Results", f"run_{session_id}")
        os.makedirs(run_folder, exist_ok=True)

        dest = os.path.join(run_folder, "input.jpg")
        shutil.copy2(image_path, dest)

        init_db()
        detector = _get_detector()
        analyzer = StyleAnalyzer(taxonomy_mode=taxonomy_mode)

        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Could not read image: {image_path}")

        crops = detector.get_person_crops(frame)
        crop = max(crops, key=lambda c: c.shape[0] * c.shape[1]) if crops else frame

        brief = analyzer.analyze(crop)
        if not brief:
            # fallback empty brief
            brief = {
                "current_outfit": [],
                "style_scores": {"keywords": {k: 0.0 for k in KEYWORDS}, "archetypes": {}},
                "coloring": {"skin_tone": "neutral", "contrast_level": "medium", "confidence": 0.0},
                "context": {"setting": "unknown", "inferred_formality": "casual", "confidence": 0.0},
                "price_tier": {"inferred_tier": "mid", "confidence": 0.0, "signals": ""},
                "overall_confidence": 0.0,
                "low_confidence_fallback": True,
                "recommendations": [],
            }

        person_id = save_analysis(dest, json.dumps(brief), brief, taxonomy_mode)

        # Save human-readable brief to run folder
        brief_path = os.path.join(run_folder, "brief.json")
        with open(brief_path, "w") as f:
            json.dump(brief, f, indent=2)

        return {
            "person_id": person_id,
            "brief": brief,
            "keywords": brief.get("style_scores", {}).get("keywords", {}),
            "run_folder": run_folder,
        }
    finally:
        os.chdir(original_cwd)
