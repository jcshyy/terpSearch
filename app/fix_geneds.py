# app/fix_geneds.py

import csv
from sqlmodel import Session, select
from app.db import engine, Course

BATCH_SIZE = 500

def main():
    path = "data/raw/courses.csv"
    print(f"Fixing geneds from {path} ...")

    updated = 0
    missing = 0

    with open(path, newline="", encoding="utf-8") as f, Session(engine) as s:
        reader = csv.DictReader(f)
        batch = 0

        for row in reader:
            course_id = row["course_id"].strip()
            raw_geneds = row.get("geneds", "")

            # normalize: pipes -> spaces, uppercase, trim
            geneds_clean = (raw_geneds or "").replace("|", " ").upper().strip()

            if not geneds_clean:
                # this course really has no geneds in CSV
                missing += 1
                continue

            course = s.get(Course, course_id)
            if not course:
                # course not found in DB for some reason
                continue

            course.geneds = geneds_clean
            s.add(course)
            updated += 1
            batch += 1

            if batch >= BATCH_SIZE:
                s.commit()
                print(f"  committed geneds for {updated} courses so far...")
                batch = 0

        if batch > 0:
            s.commit()
            print(f"  committed final batch, total updated = {updated}")

    print(f"Done. Updated geneds for {updated} courses. Missing geneds in CSV for {missing} courses.")

if __name__ == "__main__":
    main()
