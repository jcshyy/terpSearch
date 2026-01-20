from sqlmodel import SQLModel, Field, create_engine
from typing import Optional

DB_URL = 'sqlite:///data/artifacts/metadata.db'
engine = create_engine(DB_URL, echo=False)

class Course(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    description: str = ''
    credits: Optional[int] = None
    geneds: Optional[str] = None
    
    # NEW:
    avg_gpa: float | None = None
    ease_score: float | None = None
    pct_ab: float | None = None

class Professor(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    avg_rating: Optional[float] = None
    department: Optional[str] = None

class Review(SQLModel, table=True):
    id: str = Field(primary_key=True, alias="review_id")
    course_id: str | None = None
    professor_id: str | None = None
    review_text: str | None = None
    rating: float | None = None   # PlanetTerp 1..5
    term: str | None = None
    
class DocChunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: str
    kind: str
    text: str
    title: Optional[str] = None
    meta_json: Optional[str] = None

def init_db():
    SQLModel.metadata.create_all(engine)
