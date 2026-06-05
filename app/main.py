# app/main.py
from functools import lru_cache
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.search_service import HybridSearcher


app = FastAPI(title="UMD Semantic Course & Professor Search")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5199",
        "http://127.0.0.1:5199",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchResult(BaseModel):
    doc_id: str
    score: float
    kind: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    meta: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    top_k: int
    alpha: float
    results: List[SearchResult]


class CourseProfessorSummary(BaseModel):
    id: str
    name: str
    avg_rating: Optional[float] = None
    review_count: int


class CourseReviewSummary(BaseModel):
    id: str
    professor_id: Optional[str] = None
    professor_name: Optional[str] = None
    rating: Optional[float] = None
    term: Optional[str] = None
    review_text: Optional[str] = None


class CourseDetailResponse(BaseModel):
    course_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    credits: Optional[int] = None
    geneds: List[str]
    avg_gpa: Optional[float] = None
    ease_score: Optional[float] = None
    pct_ab: Optional[float] = None
    popularity: int
    planetterp_url: str
    grade_distribution: Optional[List[dict]] = None
    professors: List[CourseProfessorSummary]
    reviews: List[CourseReviewSummary]


@lru_cache(maxsize=1)
def get_searcher() -> HybridSearcher:
    return HybridSearcher.load_or_init()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = "",
    top_k: int = Query(default=10, ge=1, le=50),
    alpha: float = Query(default=0.6, ge=0.0, le=1.0),
    dept: Optional[str] = None,
    gened: Optional[str] = Query(default=None, pattern="^[A-Za-z]{4}$"),
    min_credits: Optional[int] = Query(default=None, ge=0),
    min_avg_gpa: Optional[float] = Query(default=None, ge=0.0, le=4.0),
    min_ease: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    min_popularity: Optional[int] = Query(default=None, ge=0),
    sort_by: str = Query(default="relevance", pattern="^(relevance|popularity|gpa|ease)$"),
):
    has_filter = any(
        value is not None and value != ""
        for value in [dept, gened, min_credits, min_avg_gpa, min_ease, min_popularity]
    )
    if not q.strip() and not has_filter:
        raise HTTPException(
            status_code=400,
            detail="Enter a search query or apply at least one filter.",
        )

    results = get_searcher().search(
        query=q,
        top_k=top_k,
        alpha=alpha,
        dept=dept,
        gened=gened,
        min_credits=min_credits,
        min_avg_gpa=min_avg_gpa,
        min_ease=min_ease,
        min_popularity=min_popularity,
        sort_by=sort_by,
    )

    return SearchResponse(
        query=q,
        top_k=top_k,
        alpha=alpha,
        results=[SearchResult(**r) for r in results],
    )


@app.get("/courses/{course_id}", response_model=CourseDetailResponse)
def course_detail(course_id: str):
    detail = get_searcher().get_course_detail(course_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Course not found.")
    return CourseDetailResponse(**detail)
