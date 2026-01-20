# app/ingest.py
import csv
import argparse
import math
from pathlib import Path
from sqlmodel import Session
from app.db import engine, init_db, Course, Professor, Review
from app.bm25_index import BM25Index, ARTIFACT as BM25_PATH
from app.vector_index import VectorIndex, ARTIFACT as FAISS_PATH, MAP_PATH as FAISS_MAP
from app.embedder import TextEmbedder


BATCH_SIZE = 500

# ---------- loaders ----------
def load_courses_umd(path: str):
    print(f"Loading courses from {path} ...")
    with open(path, newline="", encoding="utf-8") as f, Session(engine) as s:
        reader = csv.DictReader(f)
        batch = []
        count = 0

        for row in reader:
            cid = (row.get("course_id") or "").strip()
            if not cid:
                continue

            raw_geneds = row.get("geneds", "")
            # normalize: pipes -> spaces, uppercase, collapse whspace
            geneds_clean = " ".join((raw_geneds or "").replace("|", " ").upper().split()).strip()
            

            # GenEd-only filter
            # Treat as GenEd iff there's at least one token like DSHU, DSNS, DSSP, DVUP, SCIS, etc.
            if not geneds_clean:
                continue

            c = Course(
                id=cid,
                title=(row.get("title") or "").strip(),
                description=row.get("description") or "",
                credits=int(row["credits"]) if (row.get("credits") or "").isdigit() else None,
                geneds=geneds_clean,
            )
            batch.append(c)
            count += 1

            if len(batch) >= BATCH_SIZE:
                for obj in batch:
                    s.add(obj)
                s.commit()
                batch.clear()
                print(f"  committed {count} courses so far...")

        if batch:
            for obj in batch:
                s.add(obj)
            s.commit()
            print(f"  committed final {len(batch)} courses; total {count}.")
    print(f"Loaded UMD.io courses: {count}")

def load_professors_pt(path: str):
    n = 0
    with open(path, newline="", encoding="utf-8") as f, Session(engine) as s:
        r = csv.DictReader(f)
        for row in r:
            pid = (row.get("professor_id") or "").strip()
            if not pid:
                continue
            obj = Professor(
                id=pid,
                name=row.get("name"),
                department=row.get("department"),
                avg_rating=float(row["avg_rating"]) if row.get("avg_rating") not in (None, "", "nan") else None,
            )
            s.add(obj); n += 1
        s.commit()
    print(f"Loaded PlanetTerp profs: {n}")

def load_planetterp_reviews(path: str):
    n = 0
    with open(path, newline="", encoding="utf-8") as f, Session(engine) as s:
        r = csv.DictReader(f)
        for row in r:
            rid = (row.get("review_id") or "").strip()
            if not rid:
                continue
            obj = Review(
                id=rid,
                course_id=(row.get("course_id") or "").strip() or None,
                professor_id=(row.get("professor_id") or "").strip() or None,
                review_text=row.get("review_text"),
                rating=float(row["rating"]) if row.get("rating") not in (None, "", "nan") else None,
                term=row.get("term"),
            )
            s.add(obj); n += 1
        s.commit()
    print(f"Loaded PlanetTerp reviews: {n}")

def load_grade_distributions_pt(path: str):
    with open(path, newline="", encoding="utf-8") as f, Session(engine) as s:
        r = csv.DictReader(f)
        for row in r:
            course_id = row["course_id"].strip()
            # pull counts as ints, defaulting to 0
            A = int(row.get("A", 0) or 0)
            B = int(row.get("B", 0) or 0)
            C = int(row.get("C", 0) or 0)
            D = int(row.get("D", 0) or 0)
            F = int(row.get("F", 0) or 0)
            W = int(row.get("W", 0) or 0)

            total = A + B + C + D + F  # usually ignore W for grade difficulty

            if total == 0:
                continue

            # compute average GPA (A=4, B=3, C=2, D=1, F=0)
            avg_gpa = (4*A + 3*B + 2*C + 1*D + 0*F) / total
            pct_ab = (A + B) / total

            # normalize ease_score into 0–1 (you can tweak this)
            # assume 2.0–4.0 range of avg_gpa
            ease = max(0.0, min(1.0, (avg_gpa - 2.0) / 2.0))

            course = s.get(Course, course_id)
            if course:
                course.avg_gpa = avg_gpa
                course.pct_ab = pct_ab
                course.ease_score = ease
                s.add(course)
        s.commit()

# ---------- index builders ----------
def build_chunks():
    # Create the raw text corpus + ids used by BM25 and embeddings
    from sqlmodel import select
    texts, ids = [], []
    with Session(engine) as s:
        for c in s.exec(select(Course)).all():
            geneds_str = (c.geneds or "").replace("|", " ")
            text = f"{c.id} {c.title or ''} {c.description or ''} geneds {geneds_str}"
            texts.append(text.strip())
            ids.append(f"course:{c.id}:0")
        # (Optional) add prof/review documents similarly if you want them in search
    return texts, ids

def build_indices(texts, ids):
    print("Building indices...")
    embed = TextEmbedder()
    bm25 = BM25Index(texts, ids)
    X = embed.encode(texts)
    vindex = VectorIndex(X.shape[1])
    vindex.add(X, ids)
    bm25.save(BM25_PATH)
    vindex.save(FAISS_PATH, FAISS_MAP)
    print("Indices saved.")

# ---------- main entrypoint ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--courses", type=str, help="UMD.io courses CSV (e.g., data/raw/courses.csv)")
    ap.add_argument("--profs", type=str, help="PlanetTerp professors CSV (e.g., data/raw/professors.csv)")
    ap.add_argument("--reviews", type=str, help="PlanetTerp reviews CSV (e.g., data/raw/reviews.csv)")
    ap.add_argument("--grades", type=str)   # NEW
    args = ap.parse_args()

    init_db()

    if args.courses:
        load_courses_umd(args.courses)

    if args.profs:
        load_professors_pt(args.profs)

    if args.reviews:
        load_planetterp_reviews(args.reviews)

    # Rebuild BM25 + FAISS artifacts after loading data
    texts, ids = build_chunks()
    build_indices(texts, ids)

if __name__ == "__main__":
    main()
