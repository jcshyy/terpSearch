import os, numpy as np
import re
from typing import Dict
from sqlmodel import Session, select
from app.db import engine, init_db, Course, Professor, Review
from app.bm25_index import BM25Index, ARTIFACT as BM25_PATH
from app.vector_index import VectorIndex, ARTIFACT as FAISS_PATH, MAP_PATH as FAISS_MAP
from app.embedder import TextEmbedder


os.makedirs('data/artifacts', exist_ok=True)

GENED_KEYWORDS: Dict[str, list[str]] = {
    "i series": ["SCIS"],
    "i-series": ["SCIS"],
    "signature course": ["SCIS"],
    "signature courses": ["SCIS"],

    "humanities": ["DSHU"],
    "history and social sciences": ["DSHS"],
    "history & social sciences": ["DSHS"],
    "natural sciences": ["DSNS"],
    "natural science lab": ["DSNL"],
    "lab science": ["DSNL"],

    "scholarship in practice": ["DSSP"],
    "cultural competency": ["DVCC"],
    "understanding plural societies": ["DVUP"],

    "academic writing": ["FSAW"],
    "analytic reasoning": ["FSAR"],
    "math": ["FSMA"],
    "oral communication": ["FSOC"],
    "professional writing": ["FSPW"],
}

def wants_i_series(query: str) -> bool:
    q = query.lower()
    return any(
        phrase in q
        for phrase in [
            "i series",
            "i-series",
            "i course",
            "i-series course",
            "signature course",
            "signature courses",
        ]
    )


def augment_query_with_geneds(query: str) -> str:
    """
    If the user mentions things like 'i series', 'humanities', etc.,
    append the corresponding GenEd codes (SCIS, DSHU, ...) to the query
    so BM25 / embeddings can pull those courses into the candidate set.
    """
    q = query.lower()
    extra_codes: set[str] = set()

    for phrase, codes in GENED_KEYWORDS.items():
        if phrase in q:
            extra_codes.update(codes)

    if not extra_codes:
        return query

    # e.g. "i series" -> "i series SCIS"
    return f"{query} " + " ".join(sorted(extra_codes))



def _clean(text: str) -> str:
    if not text:
        return ""
    # strip basic HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # hide literal 'nan'
    return "" if text.lower() == "nan" else text

def compute_gened_boost(query: str, geneds: str | None) -> float:
    if not geneds:
        return 0.0

    q = query.lower()
    geneds_set = set((geneds or "").upper().split())  # e.g. "DSHU SCIS" -> {"DSHU","SCIS"}

    desired_codes = set()
    for phrase, codes in GENED_KEYWORDS.items():
        if phrase in q:
            desired_codes.update(codes)

    if not desired_codes:
        return 0.0

    overlap = geneds_set.intersection(desired_codes)
    if not overlap:
        return 0.0

    # simple 1.0 if any desired GenEd matches
    return 1.0


class HybridSearcher:
    def __init__(self, bm25: BM25Index, vindex: VectorIndex, embedder: TextEmbedder):
        self.bm25 = bm25; self.vindex = vindex; self.embedder = embedder
    @classmethod
    def load_or_init(cls):
        init_db()
        if os.path.exists(BM25_PATH) and os.path.exists(FAISS_PATH) and os.path.exists(FAISS_MAP):
            return cls(BM25Index.load(BM25_PATH), VectorIndex.load(FAISS_PATH, FAISS_MAP), TextEmbedder())
        embed = TextEmbedder()
        texts = ['Intro to Java and data structures','Discrete math: proofs and logic','Linear algebra for CS']
        ids = ['course:CMSC131:1','course:CMSC250:1','course:MATH240:1']
        bm25 = BM25Index(texts, ids); X = embed.encode(texts)
        vindex = VectorIndex(X.shape[1]); vindex.add(X, ids)
        bm25.save(BM25_PATH); vindex.save(FAISS_PATH, FAISS_MAP)
        return cls(bm25, vindex, embed)
    def _norm(self, d: Dict[str, float]) -> Dict[str, float]:
        if not d: return {}
        arr = np.array(list(d.values()), float)
        if arr.max() == arr.min(): return {k: 0.0 for k in d}
        n = (arr - arr.min()) / (arr.max() - arr.min())
        return {k: float(v) for k,v in zip(d.keys(), n.tolist())}
    def search(self, query: str, top_k: int = 10, alpha: float = 0.6,
               dept: str | None = None, min_credits: int | None = None):

        # Does the user explicitly want I-Series?
        wants_i = wants_i_series(query)

        # Augment query with GenEd codes (e.g. "i series" -> "i series SCIS")
        effective_query = augment_query_with_geneds(query)

        # 1) get candidates from both rankers using the *effective* query
        bm25_hits = self.bm25.search(effective_query, top_k=top_k * 10)
        bm25s = {i: s for i, s in bm25_hits}

        qvec = self.embedder.encode([effective_query])[0]
        vhits = self.vindex.search(qvec, top_k=top_k * 10)
        vs = {i: s for i, s in vhits}

        # 2) score fusion (BM25 + vector)
        keys = set(bm25s) | set(vs)
        b = self._norm({k: bm25s.get(k, 0.0) for k in keys})
        v = self._norm({k: vs.get(k, 0.0) for k in keys})
        fused = {
            k: alpha * b.get(k, 0.0) + (1 - alpha) * v.get(k, 0.0)
            for k in keys
        }

        # take a larger pool for re-ranking
        candidate_ids = sorted(
            fused.keys(), key=lambda k: fused[k], reverse=True
        )[: top_k * 10]

        # 3) helpers for pretty titles/snippets
        def nice_course(c: Course):
            title = f"{c.id} — {c.title}".strip(" —")
            desc = _clean(c.description or "")
            return title, (desc[:200] + ("…" if len(desc) > 200 else ""))

        def nice_prof(p: Professor):
            base = p.name or "(Unknown Professor)"
            extra = []
            if p.department:
                extra.append(p.department)
            if p.avg_rating is not None:
                extra.append(f"rating {p.avg_rating:.2f}")
            title = f"{base} — " + ", ".join(extra) if extra else base
            return title, ""

        def nice_review(r: Review):
            text = (r.review_text or "").strip()
            return "Review", (text[:200] + ("…" if len(text) > 200 else ""))

        results = []

        # 4) pull metadata & apply boosts
        ease_weight = 0.4
        gened_weight = 0.6

        # If the user explicitly wants I-Series, bypass BM25/FAISS candidates
        if wants_i:
            results = []
            with Session(engine) as s:
                courses = s.exec(select(Course)).all()

            scis_courses = []
            for c in courses:
                geneds_tokens = (c.geneds or "").upper().split()
                if "SCIS" not in geneds_tokens:
                    continue
                if dept and not c.id.upper().startswith(dept.upper()):
                    continue
                if min_credits is not None and c.credits is not None and c.credits < min_credits:
                    continue
                scis_courses.append(c)

            # build results (simple scoring for now)
            for c in scis_courses:
                title, snippet = nice_course(c)
                gboost = compute_gened_boost(query, c.geneds)
                ease = getattr(c, "ease_score", None) or 0.0
                final_score = 0.6 * gboost + 0.4 * ease

                results.append({
                    "doc_id": f"course:{c.id}:0",
                    "score": float(final_score),
                    "kind": "course",
                    "title": title,
                    "snippet": snippet,
                    "meta": {
                        "credits": c.credits,
                        "geneds": c.geneds,
                        "avg_gpa": c.avg_gpa,
                        "ease_score": ease,
                        "gened_boost": gboost,
                    },
                })

            results.sort(key=lambda r: r["score"], reverse=True)
            return results[:top_k]


        with Session(engine) as s:
            for k in candidate_ids:
                kind, mid, _chunk = k.split(":", 2)  # "course:CMSC132:123"
                base_score = float(fused.get(k, 0.0))
                title, snippet, meta = None, None, {}

                if kind == "course":
                    c = s.exec(select(Course).where(Course.id == mid)).first()
                    if not c:
                        continue

                    # simple filters
                    if dept and not c.id.upper().startswith(dept.upper()):
                        continue
                    if (
                        min_credits is not None
                        and c.credits is not None
                        and c.credits < min_credits
                    ):
                        continue

                    # --- boosts ---
                    gboost = compute_gened_boost(query, c.geneds)
                    ease = getattr(c, "ease_score", None) or 0.0  # still 0.0 for now

                    final_score = (
                        base_score
                        + ease_weight * ease
                        + gened_weight * gboost
                    )

                    title, snippet = nice_course(c)
                    meta = {
                        "credits": c.credits,
                        "geneds": c.geneds,
                        "avg_gpa": c.avg_gpa,
                        "ease_score": ease,
                        "pct_a": getattr(c,"pct_a", None),
                        "pct_ab": getattr(c,"pct_ab", None),
                        "gened_boost": gboost,
                    }

                elif kind == "prof":
                    p = s.exec(select(Professor).where(Professor.id == mid)).first()
                    if not p:
                        continue
                    final_score = base_score
                    title, snippet = nice_prof(p)
                    meta = {"department": p.department, "avg_rating": p.avg_rating}

                elif kind == "review":
                    r = s.exec(select(Review).where(Review.id == mid)).first()
                    if not r:
                        continue
                    final_score = base_score
                    title, snippet = nice_review(r)
                    meta = {
                        "course_id": r.course_id,
                        "professor_id": r.professor_id,
                        "rating": r.rating,
                        "term": r.term,
                    }

                results.append(
                    {
                        "doc_id": k,
                        "score": float(final_score),
                        "kind": kind,
                        "title": title,
                        "snippet": snippet,
                        "meta": meta,
                    }
                )

        # 5) final sort + top_k
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
