# app/sources/pt_reviews_wrapper.py
import argparse, csv, time
import pandas as pd
from planetterp.PlanetTerp import PlanetTerp

def _norm_course_id(cid: str) -> str:
    # "CMSC 131" -> "CMSC131"
    return (cid or "").replace(" ", "").strip()

def dump_reviews_from_courses(courses_csv: str, out_reviews_csv: str, limit: int | None = None):
    df = pd.read_csv(courses_csv)
    if "course_id" not in df.columns:
        raise SystemExit("Expected a 'course_id' column in courses.csv")

    pt = PlanetTerp()
    seen = set()
    written = 0
    checked = 0

    

    with open(out_reviews_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["review_id", "course_id", "professor_id", "review_text", "rating", "term"],
        )
        w.writeheader()

        for _, row in df.iterrows():
            cid = _norm_course_id(str(row["course_id"]))
            if not cid:
                continue

            # retry a couple times for transient failures / rate limit
            for attempt in range(3):
                try:
                    data = pt.course(cid, reviews=True)  # wrapper handles the GET for /course?name=...&reviews=true
                    break
                except Exception:
                    data = None
                    time.sleep(0.6 * (attempt + 1))

            checked += 1
            if not isinstance(data, dict):
                continue

            for r in (data.get("reviews") or []):
                rid = str(r.get("id") or "").strip()
                if not rid or rid in seen:
                    continue
                seen.add(rid)

                w.writerow({
                    "review_id": rid,
                    "course_id": r.get("course"),
                    "professor_id": r.get("professor") or r.get("professor_name"),
                    "review_text": r.get("review"),
                    "rating": r.get("rating"),
                    "term": r.get("semester"),
                })
                written += 1
                if limit and written >= limit:
                    print(f"[stop] hit limit {written}")
                    return written

            if checked % 25 == 0:
                print(f"...checked {checked} courses; wrote {written} reviews")
            time.sleep(0.12)  # be polite

    print(f"[done] checked {checked} courses; wrote {written} reviews")
    return written

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="incsv", required=True, help="Path to data/raw/courses.csv (UMD.io)")
    ap.add_argument("--out", dest="outcsv", required=True, help="Path to write data/raw/reviews.csv")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    n = dump_reviews_from_courses(args.incsv, args.outcsv, args.limit)
    print(f"Reviews written: {n}")
