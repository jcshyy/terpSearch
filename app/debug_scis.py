# app/debug_scis.py
from sqlmodel import Session, select
from app.db import engine, Course

def main():
    with Session(engine) as s:
        courses = s.exec(select(Course)).all()
    scis = [c for c in courses if "SCIS" in ((c.geneds or "").upper().split())]
    print("Total courses:", len(courses))
    print("SCIS courses:", len(scis))
    for c in scis[:20]:
        print(c.id, repr(c.geneds))

if __name__ == "__main__":
    main()