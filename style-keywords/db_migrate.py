"""
db_migrate.py — Adds ratings and favorites tables to fashion.db.
Safe to re-run — all CREATE statements use IF NOT EXISTS.

Usage:
    python3 db_migrate.py
"""

import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "fashion.db")

# ── schema ────────────────────────────────────────────────────────────────────

CREATE_RATINGS = """
CREATE TABLE IF NOT EXISTS ratings (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id     TEXT    NOT NULL,
  person_id      INTEGER NOT NULL,
  product_id     TEXT    NOT NULL,
  contextual_fit INTEGER CHECK(contextual_fit BETWEEN 1 AND 5),
  general_taste  INTEGER CHECK(general_taste BETWEEN 1 AND 5),
  created_at     TEXT    NOT NULL,
  FOREIGN KEY (person_id)  REFERENCES person_analysis(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
)
"""

CREATE_FAVORITES = """
CREATE TABLE IF NOT EXISTS favorites (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT    NOT NULL,
  person_id   INTEGER NOT NULL,
  product_id  TEXT    NOT NULL,
  created_at  TEXT    NOT NULL,
  -- max 5 favorites per session is enforced in the application layer, not here
  FOREIGN KEY (person_id)  REFERENCES person_analysis(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
)
"""

CREATE_IDX_RATINGS = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_session_product
ON ratings(session_id, product_id)
"""

CREATE_IDX_FAVORITES = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_session_product
ON favorites(session_id, product_id)
"""

# tables to verify and the db file each lives in
VERIFY_TABLES = [
    ("products",        DB_PATH),
    ("ratings",         DB_PATH),
    ("favorites",       DB_PATH),
]


def row_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def main():
    # ── preflight ─────────────────────────────────────────────────────────────
    if not os.path.isfile(DB_PATH):
        print("[ERROR] fashion.db not found. Run migrate.py first.")
        sys.exit(1)

    print(f"[DB] Connecting to {os.path.basename(DB_PATH)}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # ── create tables ─────────────────────────────────────────────────────────
    for name, ddl in [("ratings", CREATE_RATINGS), ("favorites", CREATE_FAVORITES)]:
        print(f"[DB] Creating table: {name}...", end=" ", flush=True)
        conn.execute(ddl)
        print("done")

    # ── create indexes ────────────────────────────────────────────────────────
    for name, ddl in [
        ("idx_ratings_session_product",   CREATE_IDX_RATINGS),
        ("idx_favorites_session_product", CREATE_IDX_FAVORITES),
    ]:
        print(f"[DB] Creating index: {name}...", end=" ", flush=True)
        conn.execute(ddl)
        print("done")

    conn.commit()

    # ── verify ────────────────────────────────────────────────────────────────
    print("[DB] Verifying tables...")
    all_ok = True
    for table, db in VERIFY_TABLES:
        c = sqlite3.connect(db)
        exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists:
            count = row_count(c, table)
            print(f"  ✓ {table:<20} ({count} rows)")
        else:
            print(f"  ✗ {table:<20} MISSING in {os.path.basename(db)}")
            all_ok = False
        c.close()

    if all_ok:
        print("[DB] All tables verified")
    else:
        print("[DB] Some tables are missing — check output above")

    # ── summary ───────────────────────────────────────────────────────────────
    print()
    print("─" * 41)
    print("Migration complete")
    print("─" * 41)
    print(f"New tables created:   ratings, favorites")
    print(f"Indexes created:      2")
    print(f"Existing data:        untouched")
    print("─" * 41)

    conn.close()


if __name__ == "__main__":
    main()
