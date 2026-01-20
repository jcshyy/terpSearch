# app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from fastapi.middleware.cors import CORSMiddleware

from app.search_service import HybridSearcher


app = FastAPI(title="UMD Semantic Course & Professor Search")

# How much to let "ease" influence ranking (0.0 = ignore, 1.0 = only ease)
EASE_WEIGHT = 0.15

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

searcher = HybridSearcher.load_or_init()


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


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _ease_from_meta(meta: Optional[Dict[str, Any]]) -> float:
    """
    Pull ease_score (0..1) from the result meta if present.
    If missing, return neutral 0.5.
    """
    if not meta:
        return 0.5

    ease = meta.get("ease_score", None)
    if ease is None:
        return 0.5

    try:
        return _clamp01(float(ease))
    except Exception:
        return 0.5


def _normalize_scores(results: List[Dict[str, Any]]) -> List[float]:
    """
    Normalize current search scores into [0,1] range so mixing is stable.
    If all scores are equal or list is empty, return 0.5 for all.
    """
    if not results:
        return []

    scores = []
    for r in results:
        try:
            scores.append(float(r.get("score", 0.0)))
        except Exception:
            scores.append(0.0)

    lo = min(scores)
    hi = max(scores)
    if hi - lo == 0:
        return [0.5 for _ in scores]

    return [(_clamp01((s - lo) / (hi - lo))) for s in scores]


@app.get("/search", response_model=SearchResponse)
def search(
    q: str,
    top_k: int = 10,
    alpha: float = 0.6,
    dept: Optional[str] = None,
    min_credits: Optional[int] = None,
):
    # 1) get base hybrid results
    results = searcher.search(q, top_k=top_k, alpha=alpha, dept=dept, min_credits=min_credits)

    # 2) re-rank ONLY courses using ease_score
    #    (professor docs and anything else keep original score)
    norm_scores = _normalize_scores(results)

    for i, r in enumerate(results):
        kind = (r.get("kind") or "").lower()
        if kind != "course":
            continue

        rel = norm_scores[i]  # normalized relevance in [0,1]
        ease = _ease_from_meta(r.get("meta"))

        final_score = (1.0 - EASE_WEIGHT) * rel + EASE_WEIGHT * ease

        # store helpful debugging fields (won't break schema)
        r["rel_score"] = rel
        if r.get("meta") is None:
            r["meta"] = {}
        r["meta"]["ease_score_used"] = ease

        # overwrite score with the combined score
        r["score"] = final_score

    # 3) final sort + cut to top_k (in case re-ranking changed order)
    results.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    results = results[:top_k]

    return SearchResponse(
        query=q,
        top_k=top_k,
        alpha=alpha,
        results=[SearchResult(**r) for r in results],
    )
