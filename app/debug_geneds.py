# app/debug_geneds.py

from sqlmodel import Session, select
from app.db import engine, Course

def main():
    with Session(engine) as s:
        rows = s.exec(
            select(Course).where(Course.geneds != "").limit(10)
        ).all()
        print("Non-empty geneds rows:", len(rows))
        for c in rows:
            print(c.id, repr(c.geneds))

if __name__ == "__main__":
    main()
