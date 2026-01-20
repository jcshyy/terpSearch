# app/fetch_planetterp_grades.py
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests
from sqlmodel import Session, select

from app.db import engine, Course

BASE = "https://planetterp.com/api/v1/grades"
CACHE_PATH = "data/artifacts/planetterp_grades_cache.json"

# PlanetTerp provides COUNTS for these keys per row
GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}
AB_KEYS = {"A+", "A", "A-", "B+", "B", "B-"}


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1.0 else x


def norm_course_id(cid: str) -> str:
    return (cid or "").strip().upper()


def load_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_PATH):
        return {"done": {}, "meta": {}}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"done": {}, "meta": {}}
        data.setdefault("done", {})
        data.setdefault("meta", {})
        return data
    except Exception:
        return {"done": {}, "meta": {}}


def save_cache(cache: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def compute_from_rows(rows: list[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float], int]:
    """
    rows: list of dicts like:
      {"course":"CMSC216","professor":"...","semester":"201201","A+":0,"A":2,...,"F":1,"W":3,"Other":0}
    returns (avg_gpa, pct_ab, total_graded)
    total_graded excludes W/Other (only A+..F)
    """
    totals = {k: 0 for k in list(GRADE_POINTS.keys()) + ["W", "Other"]}

    for r in rows:
        if not isinstance(r, dict):
            continue
        for k in totals:
            try:
                totals[k] += int(r.get(k, 0) or 0)
            except Exception:
                pass

    total_graded = sum(totals[k] for k in GRADE_POINTS.keys())
    if total_graded <= 0:
        return (None, None, 0)

    weighted = 0.0
    for letter, pts in GRADE_POINTS.items():
        weighted += pts * totals[letter]
    avg_gpa = weighted / total_graded

    ab = sum(totals[k] for k in AB_KEYS)
    pct_ab = ab / total_graded

    return (avg_gpa, pct_ab, total_graded)


def fetch_course_grades(sess: requests.Session, cid: str, timeout_s: float = 30.0) -> Tuple[int, Any]:
    """
    Returns (status_code, json_or_text)
    """
    r = sess.get(BASE, params={"course": cid}, timeout=timeout_s)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def main(
    sleep_s: float = 0.2,
    limit_courses: int | None = None,
    checkpoint_every: int = 50,
):
    os.makedirs("data/artifacts", exist_ok=True)

    # --- read DB courses ---
    with Session(engine) as db:
        db_courses = db.exec(select(Course)).all()

    # We'll aggregate by "base id" (strip trailing H) so AAAS100 and AAAS100H share one GPA bucket.
    base_ids: list[str] = []
    for c in db_courses:
        cid = norm_course_id(c.id)
        if cid.endswith("H") and len(cid) > 1:
            cid = cid[:-1]
        base_ids.append(cid)

    # unique, stable order
    base_ids = sorted(set(base_ids))

    if limit_courses is not None:
        base_ids = base_ids[:limit_courses]

    print(f"DB courses: {len(db_courses)} (base ids: {len(base_ids)})")

    cache = load_cache()
    done: Dict[str, Any] = cache.get("done", {})

    print(f"Loaded cache: {len(done)} base-courses already processed")

    sess = requests.Session()

    processed = 0
    newly_done = 0

    for base in base_ids:
        processed += 1
        if base in done:
            continue

        # Try base (e.g., AAAS100). If no data, this will be 400 or empty list.
        status, data = fetch_course_grades(sess, base)

        if status == 200 and isinstance(data, list) and len(data) > 0:
            avg_gpa, pct_ab, total_graded = compute_from_rows(data)
            done[base] = {
                "avg_gpa": avg_gpa,
                "pct_ab": pct_ab,
                "total_graded": total_graded,
                "status": 200,
            }
        elif status == 200 and isinstance(data, list) and len(data) == 0:
            # valid request but no rows
            done[base] = {"avg_gpa": None, "pct_ab": None, "total_graded": 0, "status": 200}
        else:
            # 400 is common when PlanetTerp has no grade data / unrecognized
            done[base] = {"avg_gpa": None, "pct_ab": None, "total_graded": 0, "status": status}

        newly_done += 1

        if newly_done % checkpoint_every == 0:
            cache["done"] = done
            save_cache(cache)
            print(f"  checkpoint: processed {processed}/{len(base_ids)}; cached {len(done)} base-courses")

        if sleep_s:
            time.sleep(sleep_s)

    cache["done"] = done
    save_cache(cache)
    print(f"Saved cache -> {CACHE_PATH} ({len(done)} base-courses).")

    # --- build GPA map from cache values that exist ---
    gpa_items = {k: v for k, v in done.items() if isinstance(v, dict) and v.get("avg_gpa") is not None}
    if not gpa_items:
        print("No GPA values found in cache (PlanetTerp returned none for your set).")
        return

    gpas = [float(v["avg_gpa"]) for v in gpa_items.values()]
    lo, hi = min(gpas), max(gpas)
    denom = (hi - lo) if hi != lo else 1.0

    # --- write back to DB ---
    with Session(engine) as db:
        updated = 0
        for c in db.exec(select(Course)).all():
            cid = norm_course_id(c.id)
            base = cid[:-1] if cid.endswith("H") and len(cid) > 1 else cid

            info = done.get(base)
            if not info or info.get("avg_gpa") is None:
                continue

            c.avg_gpa = float(info["avg_gpa"])
            c.ease_score = clamp01((c.avg_gpa - lo) / denom)

            if hasattr(c, "pct_ab"):
                c.pct_ab = float(info["pct_ab"]) if info.get("pct_ab") is not None else None

            db.add(c)
            updated += 1

        db.commit()

    print(f"Updated {updated} courses with avg_gpa + ease_score (+ pct_ab if exists).")
    print(f"GPA range used: {lo:.3f} to {hi:.3f}")


if __name__ == "__main__":
    # start conservative to avoid rate limits; later you can drop sleep_s
    main(sleep_s=0.2, limit_courses=None, checkpoint_every=50)
