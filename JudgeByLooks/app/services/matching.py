import os
import sys
import json
import sqlite3
from datetime import datetime

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)
FASHION_DB  = os.path.join(STYLE_KEYWORDS_DIR, "fashion.db")
KEYWORDS_DB = os.path.join(STYLE_KEYWORDS_DIR, "keywords.db")

TIER_ORDER = ["budget", "mid", "premium", "luxury"]


def _gender_match(product: dict, person_gender: str) -> bool:
    """Return True if product gender is compatible with the person's gender."""
    pg = (product.get("gender") or "unisex").lower()
    if pg == "unisex" or person_gender == "unisex":
        return True
    return pg == person_gender


def _ensure_path():
    if STYLE_KEYWORDS_DIR not in sys.path:
        sys.path.insert(0, STYLE_KEYWORDS_DIR)


# ── price-tier helpers ────────────────────────────────────────────────────────

def _tier_targets(inferred_tier: str, strategy: str, tier_shift: int = 0) -> list[str]:
    """Return list of acceptable price_tier values given strategy."""
    if strategy == "ignore":
        return TIER_ORDER[:]
    if strategy == "match":
        return [inferred_tier] if inferred_tier in TIER_ORDER else TIER_ORDER[:]
    if strategy == "mixed":
        idx = TIER_ORDER.index(inferred_tier) if inferred_tier in TIER_ORDER else 1
        tiers = [TIER_ORDER[idx]]
        if idx + 1 < len(TIER_ORDER):
            tiers.append(TIER_ORDER[idx + 1])
        return tiers
    if strategy in ("above", "below"):
        if inferred_tier not in TIER_ORDER:
            return TIER_ORDER[:]
        idx = TIER_ORDER.index(inferred_tier)
        shift = tier_shift if tier_shift > 0 else 1
        new_idx = idx + shift if strategy == "above" else idx - shift
        new_idx = max(0, min(len(TIER_ORDER) - 1, new_idx))
        return [TIER_ORDER[new_idx]]
    return TIER_ORDER[:]


# ── redundancy check ──────────────────────────────────────────────────────────

def _is_redundant(product: dict, current_outfit: list[dict]) -> bool:
    """True if product closely duplicates something already worn."""
    p_type   = (product.get("item_type") or "").lower()
    p_color  = (product.get("color_family") or "").lower()
    p_sil    = (product.get("silhouette_attr") or "").lower()
    for item in current_outfit:
        same_type  = (item.get("item_type") or "").lower() == p_type
        same_color = (item.get("color_family") or "").lower() == p_color
        same_sil   = (item.get("silhouette") or "").lower() == p_sil
        if same_type and (same_color or same_sil):
            return True
    return False


# ── attribute match score ─────────────────────────────────────────────────────

def _attr_match(product: dict, target: dict) -> float:
    """0–1 score: fraction of target_attributes that match the product's Layer-1 fields."""
    checks = [
        ("item_type",      "item_type"),
        ("color_family",   "color_family"),
        ("silhouette_attr","silhouette"),
        ("fabric_attr",    "fabric"),
        ("formality_attr", "formality"),
    ]
    hits = 0
    for prod_key, tgt_key in checks:
        prod_val = (product.get(prod_key) or "").lower()
        tgt_val  = (target.get(tgt_key) or "").lower()
        if prod_val and tgt_val and prod_val == tgt_val:
            hits += 1
    return hits / len(checks)


# ── archetype/keyword style filter ───────────────────────────────────────────

def _style_score(product: dict, style_scores: dict, taxonomy_mode: str) -> float:
    """Return a style compatibility score [0,1] between product and person style_scores."""
    score = 0.0
    if taxonomy_mode in ("archetypes", "both"):
        arch = style_scores.get("archetypes", {})
        for arch_id, person_weight in arch.items():
            prod_arch = product.get(f"arch_{arch_id}", 0.0) or 0.0
            score += float(person_weight) * float(prod_arch)
    if taxonomy_mode in ("keywords", "both"):
        from match import KEYWORDS, cosine, row_to_vec
        kw = style_scores.get("keywords", {})
        if kw:
            person_vec = [float(kw.get(k, 0.0)) for k in KEYWORDS]
            prod_vec   = row_to_vec(product)
            kw_score   = cosine(person_vec, prod_vec)
            score = (score + kw_score) / 2 if taxonomy_mode == "both" else kw_score
    return float(score)


# ── Mode 1: similarity baseline ───────────────────────────────────────────────

def _run_similarity(person: dict, products: list[dict], params: dict) -> list[dict]:
    """Cosine similarity on 72-keyword vectors — existing baseline."""
    from match import KEYWORDS, cosine, row_to_vec, diverse_top, top_keywords

    person_vec = row_to_vec(person)
    person_gender = params.get("gender", "unisex")
    inferred_tier = json.loads(person.get("price_tier_brief") or "{}").get("inferred_tier", "mid")
    tier_targets = _tier_targets(
        inferred_tier,
        params.get("price_tier_strategy", "match"),
        int(params.get("tier_shift", 0)),
    )

    ranked = []
    for p in products:
        if p.get("price_tier") not in tier_targets:
            continue
        if not _gender_match(p, person_gender):
            continue
        score = cosine(person_vec, row_to_vec(p))
        ranked.append((score, p))

    ranked.sort(key=lambda x: -x[0])
    results = diverse_top(ranked, 10)

    recs = []
    for i, (score, p) in enumerate(results):
        kws = top_keywords(row_to_vec(p), 5)
        recs.append({
            "rank": i + 1,
            "score": round(score, 4),
            "product_id": p.get("id"),
            "brand": p.get("brand") or "",
            "name": p.get("name") or "",
            "category": p.get("category") or "",
            "price": p.get("price") or 0.0,
            "currency": p.get("currency") or "",
            "price_tier": p.get("price_tier") or "",
            "product_url": p.get("product_url") or "",
            "image_url": p.get("image_url") or "",
            "top_keywords": kws,
            "retrieval_mode": "similarity",
        })
    return recs


# ── Mode 2: gap-based stylist retrieval ───────────────────────────────────────

def _run_gap_based(person: dict, products: list[dict], brief: dict, params: dict) -> list[dict]:
    """
    Per-slot retrieval driven by recommendations[].target_attributes from the stylist brief.
    For each slot: attribute filter → style filter → redundancy check → price-tier filter → rank.
    Across slots: diversity by item_type.
    """
    recommendations = brief.get("recommendations", [])
    current_outfit  = brief.get("current_outfit", [])
    style_scores    = brief.get("style_scores", {})
    taxonomy_mode   = params.get("taxonomy_mode", "both")
    low_conf        = brief.get("low_confidence_fallback", False)
    person_gender   = brief.get("gender", params.get("gender", "unisex"))

    inferred_tier = brief.get("price_tier", {}).get("inferred_tier", "mid")
    tier_targets = _tier_targets(
        inferred_tier,
        params.get("price_tier_strategy", "match"),
        int(params.get("tier_shift", 0)),
    )

    if not recommendations:
        # fall back to similarity if no recommendations in brief
        return _run_similarity(person, products, params)

    all_recs = []
    seen_product_ids = set()

    for slot_rec in recommendations:
        target = slot_rec.get("target_attributes", {})
        slot   = slot_rec.get("slot", "unknown")

        slot_candidates = []
        for p in products:
            if p.get("id") in seen_product_ids:
                continue
            if p.get("price_tier") not in tier_targets:
                continue
            if not _gender_match(p, person_gender):
                continue
            if _is_redundant(p, current_outfit):
                continue

            attr_score = _attr_match(p, target)
            if attr_score < 0.2:  # must match at least 1 of 5 attrs
                continue

            if low_conf:
                # low confidence: color+formality only, skip style filter
                style_sc = attr_score
            else:
                style_sc = _style_score(p, style_scores, taxonomy_mode)

            combined = 0.6 * attr_score + 0.4 * style_sc
            slot_candidates.append((combined, p, slot))

        slot_candidates.sort(key=lambda x: -x[0])
        for score, p, s in slot_candidates[:3]:
            if p.get("id") not in seen_product_ids:
                all_recs.append((score, p, s, slot_rec.get("reasoning", "")))
                seen_product_ids.add(p.get("id"))

    # Diversity: cap per item_type, guarantee 2 footwear slots
    FOOTWEAR_TYPES = {"shoes", "boots", "sneakers", "sandals", "footwear"}
    TYPE_CAP = 1        # max per non-footwear type from gap-based candidates
    FOOTWEAR_CAP = 2    # guaranteed footwear slots

    by_type: dict[str, list] = {}
    for score, p, slot, reasoning in all_recs:
        itype = (p.get("item_type") or "other").lower()
        by_type.setdefault(itype, []).append((score, p, slot, reasoning))

    final = []
    # add up to TYPE_CAP per non-footwear type
    for itype, items in by_type.items():
        if itype in FOOTWEAR_TYPES:
            continue
        items.sort(key=lambda x: -x[0])
        final.extend(items[:TYPE_CAP])

    final.sort(key=lambda x: -x[0])
    final = final[:8]  # leave 2 slots for footwear

    # fill footwear slots (guaranteed 2) — relax price tier if catalog is thin
    used_ids = {p.get("id") for _, p, _, _ in final}
    from match import KEYWORDS, cosine, row_to_vec
    person_vec = row_to_vec(person)

    def _footwear_pool(tier_filter):
        pool = []
        for p in products:
            if (p.get("item_type") or "").lower() not in FOOTWEAR_TYPES:
                continue
            if p.get("id") in used_ids:
                continue
            if tier_filter and p.get("price_tier") not in tier_filter:
                continue
            if not _gender_match(p, person_gender):
                continue
            pool.append((cosine(person_vec, row_to_vec(p)), p))
        return pool

    footwear_candidates = _footwear_pool(tier_targets)
    if len(footwear_candidates) < 2:
        # not enough in preferred tier — open up to all tiers
        footwear_candidates = _footwear_pool(None)
    footwear_candidates.sort(key=lambda x: -x[0])
    for score, p in footwear_candidates[:2]:
        final.append((score, p, "footwear_fill", ""))
        used_ids.add(p.get("id"))

    final.sort(key=lambda x: -x[0])

    # fill any remaining slots up to 10
    if len(final) < 10:
        fallback = []
        for p in products:
            if p.get("id") in used_ids:
                continue
            if p.get("price_tier") not in tier_targets:
                continue
            if not _gender_match(p, person_gender):
                continue
            score = cosine(person_vec, row_to_vec(p))
            fallback.append((score, p))
        fallback.sort(key=lambda x: -x[0])
        for score, p in fallback[:10 - len(final)]:
            final.append((score, p, "similarity_fill", ""))

    recs = []
    for i, (score, p, slot, reasoning) in enumerate(final):
        recs.append({
            "rank": i + 1,
            "score": round(score, 4),
            "product_id": p.get("id"),
            "brand": p.get("brand") or "",
            "name": p.get("name") or "",
            "category": p.get("category") or "",
            "price": p.get("price") or 0.0,
            "currency": p.get("currency") or "",
            "price_tier": p.get("price_tier") or "",
            "product_url": p.get("product_url") or "",
            "image_url": p.get("image_url") or "",
            "slot": slot,
            "slot_reasoning": reasoning,
            "top_keywords": [],
            "retrieval_mode": "gap_based",
        })
    return recs


# ── public entry point ────────────────────────────────────────────────────────

def run_matching(
    person_id: int,
    run_folder: str,
    brief: dict = None,
    params: dict = None,
) -> list[dict]:
    """
    params keys (all optional):
        retrieval_mode        "similarity" | "gap_based"  (default: gap_based)
        taxonomy_mode         "keywords" | "archetypes" | "both"
        price_tier_strategy   "match" | "above" | "below" | "mixed" | "ignore"
        tier_shift            int (used with above/below)
        silhouette_adjustment bool (logged; affects target_attributes already in brief)
    """
    _ensure_path()

    if params is None:
        params = {}
    retrieval_mode = params.get("retrieval_mode", "gap_based")

    from match import KEYWORDS, cosine, row_to_vec, diverse_top, top_keywords

    conn = sqlite3.connect(KEYWORDS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM person_analysis WHERE id = ?", (person_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"person_analysis id={person_id} not found")
    person = dict(row)

    conn = sqlite3.connect(FASHION_DB)
    conn.row_factory = sqlite3.Row
    products = [dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    conn.close()

    if not products:
        return []

    if retrieval_mode == "similarity" or not brief:
        recs = _run_similarity(person, products, params)
        mode_label = "similarity"
    else:
        recs = _run_gap_based(person, products, brief, params)
        mode_label = "gap_based"

    now = datetime.now().isoformat()
    session_id = params.get("session_id", "")
    conn = sqlite3.connect(FASHION_DB)
    conn.execute("DELETE FROM recommendations WHERE person_id = ?", (person_id,))
    for r in recs:
        conn.execute(
            """INSERT INTO recommendations
               (session_id, person_id, product_id, rank, score, mode, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, person_id, r["product_id"], r["rank"], r["score"], mode_label, now),
        )
    conn.commit()
    conn.close()

    # log experimental parameters
    try:
        from storage import log_experiment
        log_experiment(
            person_id,
            session_id,
            {**params, "retrieval_mode": mode_label},
            [r["product_id"] for r in recs],
        )
    except Exception:
        pass

    return recs
