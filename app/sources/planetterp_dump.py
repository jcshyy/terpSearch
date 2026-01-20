# app/sources/planetterp_dump.py
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import httpx

BASE = "https://planetterp.com/api/v1"
HEADERS = {
    "User-Agent": "UMD-Semantic-Search/1.0",
    "Accept": "application/json",
}

LIST_LIMIT = 100


def fetch_json(
    path_or_url: str,
    params: Dict[str, Any] | None = None,
    retries: int = 4,
    backoff_s: float = 1.25,
) -> Any | None:
    if not path_or_url.startswith("http"):
        url = f"{BASE}/{path_or_url.lstrip('/')}"
    else:
        url = path_or_url

    for attempt in range(retries):
        try:
            r = httpx.get(
                url,
                params=params or {},
                headers=HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
            ctype = (r.headers.get("content-type") or "").lower()
            if r.status_code == 200 and "application/json" in ctype:
                try:
                    return r.json()
                except json.JSONDecodeError:
                    return None

            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff_s * (attempt + 1))
                continue

            return None
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError):
            time.sleep(backoff_s * (attempt + 1))
            continue

    return None


def iter_professors(
    department: Optional[str] = None,
    max_pages: Optional[int] = None,   # number of batches
    list_limit: int = LIST_LIMIT,
) -> Iterable[Dict[str, Any]]:
    offset = 0
    page = 0
    while True:
        page += 1
        if max_pages is not None and page > max_pages:
            break

        params: Dict[str, Any] = {"limit": list_limit, "offset": offset}
        if department:
            params["department"] = department

        data = fetch_json("professors", params=params)
        if not isinstance(data, list) or not data:
            break

        for prof in data:
            yield prof

        if len(data) < list_limit:
            break

        offset += list_limit
        time.sleep(0.2)


def iter_courses(
    department: Optional[str] = None,
    max_pages: Optional[int] = None,   # number of batches
    list_limit: int = LIST_LIMIT,
) -> Iterable[Dict[str, Any]]:
    offset = 0
    page = 0
    while True:
        page += 1
        if max_pages is not None and page > max_pages:
            break

        params: Dict[str, Any] = {"limit": list_limit, "offset": offset}
        if department:
            params["department"] = department

        data = fetch_json("courses", params=params)
        if not isinstance(data, list) or not data:
            break

        for c in data:
            yield c

        if len(data) < list_limit:
            break

        offset += list_limit
        time.sleep(0.2)


def iter_reviews_for_course(course_id: str) -> Iterable[Dict[str, Any]]:
    data = fetch_json("course", params={"name": course_id, "reviews": "true"})
    if not isinstance(data, dict):
        return
    for r in (data.get("reviews") or []):
        yield r


def iter_reviews_for_prof(name: str) -> Iterable[Dict[str, Any]]:
    data = fetch_json("professor", params={"name": name, "reviews": "true"})
    if not isinstance(data, dict):
        return
    for r in (data.get("reviews") or []):
        yield r


def dump_to_csv(
    out_dir: Path,
    limit: Optional[int] = None,          # dev cap per section (profs/courses/reviews written)
    department: Optional[str] = None,
    max_pages: Optional[int] = None,      # caps list batches for profs/courses
    reviews_mode: str = "auto",           # 'auto' | 'course' | 'prof'
    verbose: bool = True,
    debug_reviews: bool = False,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    profs_fp = out_dir / "professors.csv"
    courses_fp = out_dir / "courses_pt.csv"
    reviews_fp = out_dir / "reviews.csv"

    # ---------- Professors ----------
    if verbose:
        print("Fetching professors...", end="", flush=True)
    pfields = ["professor_id", "name", "avg_rating", "department"]
    seen_prof: set[str] = set()
    prof_count = 0

    with profs_fp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pfields)
        w.writeheader()

        for p in iter_professors(department=department, max_pages=max_pages):
            pid = (p.get("slug") or p.get("id") or p.get("name") or "").strip()
            if not pid or pid in seen_prof:
                continue
            seen_prof.add(pid)

            w.writerow({
                "professor_id": pid,
                "name": p.get("name"),
                "avg_rating": p.get("average_rating"),
                "department": p.get("department"),
            })
            prof_count += 1
            if limit and prof_count >= limit:
                break

    if verbose:
        print(f" done ({prof_count}).")

    # ---------- Courses ----------
    if verbose:
        print("Fetching courses...", end="", flush=True)
    cfields = ["course_id", "title", "description", "credits", "geneds"]
    seen_course: set[str] = set()
    course_count = 0

    with courses_fp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cfields)
        w.writeheader()

        for x in iter_courses(department=department, max_pages=max_pages):
            cid = (x.get("name") or x.get("course") or "").strip()
            if not cid or cid in seen_course:
                continue
            seen_course.add(cid)

            w.writerow({
                "course_id": cid,
                "title": x.get("title"),
                "description": x.get("description"),
                "credits": x.get("credits"),
                "geneds": "|".join(x.get("geneds", []) or []),
            })
            course_count += 1
            if limit and course_count >= limit:
                break

    if verbose:
        print(f" done ({course_count}).")

    # ---------- Reviews ----------
    if verbose:
        print("Fetching reviews by", end=" ", flush=True)

    import pandas as pd
    rfields = ["review_id", "course_id", "professor_id", "review_text", "rating", "term"]
    seen_review: set[str] = set()
    written = 0

    with reviews_fp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rfields)
        w.writeheader()

        did_any = False

        # Prefer by course
        if reviews_mode in ("auto", "course"):
            if verbose:
                print("course...", end="", flush=True)

            courses_df = pd.read_csv(courses_fp)
            for _, crow in courses_df.iterrows():
                cid = str(crow.get("course_id") or "").strip()
                if not cid:
                    continue

                if debug_reviews:
                    d = fetch_json("course", params={"name": cid, "reviews": "true"})
                    if isinstance(d, dict):
                        rc = len(d.get("reviews") or [])
                        if rc > 0:
                            print(f"\n  {cid}: {rc} reviews")

                for r in iter_reviews_for_course(cid):
                    rid = str(r.get("id") or "").strip()
                    if not rid or rid in seen_review:
                        continue
                    seen_review.add(rid)

                    prof_name = (r.get("professor") or r.get("professor_name") or "").strip()

                    w.writerow({
                        "review_id": rid,
                        "course_id": cid,   # force to the course we asked for
                        "professor_id": prof_name,
                        "review_text": r.get("review"),
                        "rating": r.get("rating"),
                        "term": r.get("semester"),
                    })
                    written += 1
                    did_any = True
                    if limit and written >= limit:
                        break

                if limit and written >= limit:
                    break

        # Fallback by professor
        if (reviews_mode in ("auto", "prof")) and (not did_any or reviews_mode == "prof"):
            if verbose:
                print("professor...", end="", flush=True)

            prof_df = pd.read_csv(profs_fp)
            for _, prow in prof_df.iterrows():
                name = str(prow.get("name") or "").strip()
                pid = str(prow.get("professor_id") or "").strip()
                if not name:
                    continue

                for r in iter_reviews_for_prof(name):
                    rid = str(r.get("id") or "").strip()
                    if not rid or rid in seen_review:
                        continue
                    seen_review.add(rid)

                    w.writerow({
                        "review_id": rid,
                        "course_id": (r.get("course") or "").strip() or None,
                        "professor_id": pid or name,
                        "review_text": r.get("review"),
                        "rating": r.get("rating"),
                        "term": r.get("semester"),
                    })
                    written += 1
                    if limit and written >= limit:
                        break

                if limit and written >= limit:
                    break

    if verbose:
        print(f" done ({written}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--department", type=str, default=None)
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--reviews-mode", type=str, default="auto", choices=["auto", "course", "prof"])
    ap.add_argument("--debug-reviews", action="store_true")
    args = ap.parse_args()

    dump_to_csv(
        out_dir=Path(args.out),
        limit=args.limit,
        department=args.department,
        max_pages=args.max_pages,
        reviews_mode=args.reviews_mode,
        verbose=True,
        debug_reviews=args.debug_reviews,
    )
    print("PlanetTerp dump complete.")
