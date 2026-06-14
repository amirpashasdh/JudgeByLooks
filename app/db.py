import sqlite3
import os

_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

DB_PATH = os.getenv(
    "DB_PATH",
    "style-keywords/fashion_seed.db"
    if _ENVIRONMENT == "production"
    else "style-keywords/fashion.db",
)
KEYWORDS_DB_PATH = os.getenv("KEYWORDS_DB_PATH", "style-keywords/keywords.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_keywords_db() -> sqlite3.Connection:
    conn = sqlite3.connect(KEYWORDS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_recommendations_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            person_id   INTEGER NOT NULL,
            product_id  TEXT    NOT NULL,
            rank        INTEGER NOT NULL,
            score       REAL    NOT NULL,
            mode        TEXT    NOT NULL DEFAULT 'diverse',
            created_at  TEXT    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reco_session ON recommendations(session_id, person_id)"
    )
    conn.commit()
    conn.close()
