import csv
import argparse
from pathlib import Path
from typing import Iterable, Dict, Any, List, Optional
import sys, httpx

BASE = "https://api.umd.io/v1"

def iter_courses(c: httpx.Client, max_pages: Optional[int] = None) -> Iterable[Dict[str, Any]]:
    page = 1
    while True:
        r = c.get(f"{BASE}/courses", params={"page": page, "per_page": 200}, timeout=30.0)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        # yield each course from this page
        for x in data:
            yield x
        # stop early if max_pages is set
        if max_pages is not None and page >= max_pages:
            break
        page += 1

def _normalize_geneds(v) -> List[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        out: List[str] = []
        for item in v:
            if isinstance(item, list):
                out.extend([str(x) for x in item])
            else:
                out.append(str(item))
        return out
    return [str(v)]

def dump_courses(out_dir: str, max_pages: Optional[int] = None):
    out_csv = Path(out_dir) / "courses.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["course_id", "title", "description", "credits", "geneds"]
    written = 0
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        with httpx.Client(headers={"User-Agent": "UMD-Semantic-Search/1.0"}) as c:
            for x in iter_courses(c, max_pages=max_pages):
                geneds = "|".join(_normalize_geneds(x.get("gen_ed", [])))
                row = {
                    "course_id": x.get("course_id") or x.get("course") or x.get("course_number"),
                    "title": x.get("name") or x.get("title"),
                    "description": x.get("description"),
                    "credits": x.get("credits") or x.get("credit"),
                    "geneds": geneds,
                }
                if row["course_id"]:
                    w.writerow(row)
                    written += 1
    print(f"UMD.io courses dump complete. Rows written: {written}. Output: {out_csv}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, required=True, help="Output directory (e.g., data/raw)")
    ap.add_argument("--max_pages", type=int, default=None, help="Fetch only this many pages (None = all)")
    args = ap.parse_args()
    dump_courses(args.out, max_pages=args.max_pages)
