import sqlite3
import json
from datetime import datetime

DB_PATH = "keywords.db"

KEYWORDS = [
    # Aesthetic
    "minimalist", "maximalist", "classic", "avant_garde", "streetwear", "bohemian",
    "preppy", "romantic", "edgy", "quiet_luxury", "coastal", "dark_academia", "sporty",
    # Mood
    "playful", "serious", "rebellious", "elegant", "laid_back", "bold", "understated",
    "whimsical", "polished", "raw",
    # Color palette
    "neutral", "monochrome", "earth_tones", "pastel", "bold_colors", "black_forward",
    "white_forward", "jewel_tones", "multicolor",
    # Formality
    "loungewear", "casual", "smart_casual", "business_casual", "formal", "black_tie",
    # Cultural
    "parisian", "scandinavian", "italian_luxury", "japanese_minimalist",
    "american_prep", "british_heritage", "nyc_streetwear", "californian",
    # Silhouette
    "fitted", "oversized", "structured", "flowy", "layered", "cropped", "voluminous",
    # Occasion
    "everyday", "workwear", "going_out", "travel", "outdoor", "sport", "beach", "occasion",
    # Values
    "sustainable", "investment_piece", "trend_driven", "heritage_craft",
    "luxury_status", "budget_conscious", "logo_forward", "logo_free",
    "size_inclusive", "gender_neutral", "performance_tech",
]

_KW_COLUMNS = ", ".join(f"{k} REAL DEFAULT 0.0" for k in KEYWORDS)
_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS person_analysis (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path   TEXT NOT NULL,
    analysed_at  TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    {_KW_COLUMNS}
)
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    # drop old schema if it still has the previous columns
    cols = {row[1] for row in conn.execute("PRAGMA table_info(person_analysis)")}
    if cols and "image_path" not in cols:
        conn.execute("DROP TABLE person_analysis")
    conn.execute(_CREATE_TABLE)
    conn.commit()
    conn.close()


def save_analysis(image_path: str, raw_response: str, scores: dict) -> int:
    """Insert one row. scores is a sparse dict {keyword: float}."""
    full = {k: float(scores.get(k, 0.0)) for k in KEYWORDS}
    analysed_at = datetime.now().isoformat()

    cols = ["image_path", "analysed_at", "raw_response"] + KEYWORDS
    placeholders = ", ".join(["?"] * len(cols))
    values = [image_path, analysed_at, raw_response] + [full[k] for k in KEYWORDS]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        f"INSERT INTO person_analysis ({', '.join(cols)}) VALUES ({placeholders})",
        values,
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_recent(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    # check table exists and has the right schema
    cols = {row[1] for row in conn.execute("PRAGMA table_info(person_analysis)")}
    if not cols:
        conn.close()
        return []
    rows = conn.execute(
        "SELECT id, image_path, analysed_at, raw_response FROM person_analysis ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        try:
            scores = json.loads(r[3])
            scored_kws = {k: v for k, v in scores.items() if v > 0}
        except (json.JSONDecodeError, TypeError):
            scored_kws = {}
        results.append({
            "id": r[0],
            "image_path": r[1],
            "analysed_at": r[2],
            "keyword_count": len(scored_kws),
            "top_keywords": sorted(scored_kws.items(), key=lambda x: -x[1])[:5],
        })
    return results
