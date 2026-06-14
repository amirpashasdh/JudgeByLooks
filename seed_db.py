import sqlite3
import os

SRC = "style-keywords/fashion.db"
DST = "style-keywords/fashion_seed.db"

# Tables that live in fashion.db and must exist on Railway
TRANSIENT_TABLES = ["ratings", "favorites", "recommendations"]

# person_analysis lives in keywords.db (created fresh per-deploy)
KEYWORDS_DB_TABLES = ["person_analysis"]


def seed():
    if not os.path.exists(SRC):
        print(f"[Seed] ERROR: {SRC} not found. Run migrate.py first.")
        return

    if os.path.exists(DST):
        os.remove(DST)
        print(f"[Seed] Removed existing {DST}")

    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DST)

    # ── products: copy schema + all rows ─────────────────────────────────────
    schema_row = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='products'"
    ).fetchone()
    if not schema_row:
        print("[Seed] ERROR: products table not found in source DB.")
        src.close(); dst.close(); return

    dst.execute(schema_row[0])

    rows = src.execute("SELECT * FROM products").fetchall()
    if rows:
        placeholders = ",".join(["?"] * len(rows[0]))
        dst.executemany(f"INSERT INTO products VALUES ({placeholders})", rows)

    # ── Copy indexes on products ──────────────────────────────────────────────
    for idx in src.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='products' AND sql IS NOT NULL"
    ).fetchall():
        try:
            dst.execute(idx[0])
        except Exception:
            pass

    # ── Transient tables: schema only (no data) ───────────────────────────────
    for table in TRANSIENT_TABLES:
        row = src.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"
        ).fetchone()
        if row and row[0]:
            dst.execute(row[0])
            # Copy associated indexes
            for idx in src.execute(
                f"SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='{table}' AND sql IS NOT NULL"
            ).fetchall():
                try:
                    dst.execute(idx[0])
                except Exception:
                    pass

    dst.commit()
    src.close()
    dst.close()

    product_count = sqlite3.connect(DST).execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    print(f"[Seed] {DST} created")
    print(f"[Seed] Products: {product_count}")
    print(f"[Seed] Tables: products (with data), {', '.join(TRANSIENT_TABLES)} (empty)")
    print(f"[Seed] Note: person_analysis lives in keywords.db — created fresh per-session")
    print(f"[Seed] Ready to commit to git")


if __name__ == "__main__":
    seed()
