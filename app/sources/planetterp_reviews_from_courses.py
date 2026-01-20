# app/sources/planetterp_reviews_from_courses.py
import csv, json, httpx, argparse, pandas as pd, time
from pathlib import Path

API = "https://api.planetterp.com/v1"
HEADERS = {"Accept":"application/json","User-Agent":"TerpAI/1.0"}

def fetch_course_with_reviews(course_id: str, retries: int = 4, backoff: float = 1.25):
    # normalize e.g. "CMSC 131" -> "CMSC131"
    cid = (course_id or "").replace(" ", "").strip()
    for attempt in range(retries):
        try:
            r = httpx.get(
                f"{API}/course",
                params={"name": cid, "reviews": True},  # boolean True
                headers=HEADERS, timeout=30, follow_redirects=True
            )
            ctype = (r.headers.get("content-type") or "").lower()
            if r.status_code == 200 and "application/json" in ctype:
                try:
                    return r.json()
                except json.JSONDecodeError:
                    return None
            # gentle backoff for transient errors / rate limits
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff * (attempt + 1))
                continue
            return None
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout):
            time.sleep(backoff * (attempt + 1))
            continue
    return None

def dump_reviews_from_courses(courses_csv: str, out_reviews_csv: str, limit: int | None = None):
    df = pd.read_csv(courses_csv)
    # be safe about column name
    col = "course_id" if "course_id" in df.columns else ("course" if "course" in df.columns else None)
    if not col:
        raise SystemExit("courses.csv missing course_id column")

    seen_review = set()
    written = 0
    checked = 0

    with open(out_reviews_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["review_id","course_id","professor_id","review_text","rating","term"])
        w.writeheader()

        for _, row in df.iterrows():
            cid = str(row.get(col) or "").strip()
            if not cid:
                continue
            data = fetch_course_with_reviews(cid)
            checked += 1

            if data and isinstance(data, dict):
                for r in (data.get("reviews") or []):
                    rid = str(r.get("id") or "").strip()
                    if not rid or rid in seen_review:
                        continue
                    seen_review.add(rid)
                    w.writerow({
                        "review_id":   rid,
                        "course_id":   r.get("course"),
                        "professor_id": r.get("professor") or r.get("professor_name"),
                        "review_text": r.get("review"),
                        "rating":      r.get("rating"),
                        "term":        r.get("semester"),
                    })
                    written += 1
                    if limit and written >= limit:
                        print(f"[stop] hit limit: wrote {written} reviews")
                        return written

            # polite delay + progress log
            if checked % 25 == 0:
                print(f"...checked {checked} courses; reviews written so far: {written}")
            time.sleep(0.12)

    print(f"[done] checked {checked} courses; wrote {written} reviews")
    return written

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="incsv", required=True, help="Path to data/raw/courses.csv (UMD.io)")
    ap.add_argument("--out", dest="outcsv", required=True, help="Path to write reviews.csv")
    ap.add_argument("--limit", type=int, default=None, help="Optional cap on number of reviews")
    args = ap.parse_args()
    n = dump_reviews_from_courses(args.incsv, args.outcsv, args.limit)
    print(f"Reviews written: {n}")
