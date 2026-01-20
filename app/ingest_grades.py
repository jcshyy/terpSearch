# app/ingest_grades.py
import csv
from sqlmodel import Session, select
from app.db import engine, Course

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x

def main(path: str):
    # Load grade rows
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cid = (r.get("course_id") or r.get("course") or "").strip().upper()
            gpa_str = (r.get("avg_gpa") or r.get("gpa") or "").strip()
            if not cid or not gpa_str:
                continue
            try:
                gpa = float(gpa_str)
            except:
                continue
            rows.append((cid, gpa))

    if not rows:
        print("No rows read. Check header names like course_id, avg_gpa.")
        return

    # Normalize GPA -> ease_score in [0,1]
    gpas = [g for _, g in rows]
    lo, hi = min(gpas), max(gpas)
    denom = (hi - lo) if (hi - lo) != 0 else 1.0

    with Session(engine) as s:
        updated = 0
        for cid, gpa in rows:
            c = s.exec(select(Course).where(Course.id == cid)).first()
            if not c:
                continue
            c.avg_gpa = gpa
            c.ease_score = clamp01((gpa - lo) / denom)
            s.add(c)
            updated += 1
        s.commit()

    print(f"Loaded {len(rows)} grade rows, updated {updated} courses.")
    print(f"GPA range used for normalization: {lo:.3f} to {hi:.3f}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python -m app.ingest_grades data/raw/grades.csv")
        raise SystemExit(2)
    main(sys.argv[1])
