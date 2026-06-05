from __future__ import annotations

import os
import re
import json
from typing import Dict

import numpy as np
from sqlmodel import Session, select

from app.bm25_index import BM25Index, ARTIFACT as BM25_PATH
from app.db import Course, Professor, Review, engine, init_db
from app.embedder import TextEmbedder
from app.vector_index import MAP_PATH as FAISS_MAP
from app.vector_index import ARTIFACT as FAISS_PATH
from app.vector_index import VectorIndex


os.makedirs("data/artifacts", exist_ok=True)
CACHE_PATH = "data/artifacts/planetterp_grades_cache.json"

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
    q = query.lower()
    extra_codes: set[str] = set()

    for phrase, codes in GENED_KEYWORDS.items():
        if phrase in q:
            extra_codes.update(codes)

    if not extra_codes:
        return query

    return f"{query} " + " ".join(sorted(extra_codes))


def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text.lower() == "nan" else text


def compute_gened_boost(query: str, geneds: str | None) -> float:
    if not geneds:
        return 0.0

    q = query.lower()
    geneds_set = set((geneds or "").upper().split())

    desired_codes = set()
    for phrase, codes in GENED_KEYWORDS.items():
        if phrase in q:
            desired_codes.update(codes)

    if not desired_codes:
        return 0.0

    overlap = geneds_set.intersection(desired_codes)
    return 1.0 if overlap else 0.0


def _load_popularity_map() -> dict[str, int]:
    if not os.path.exists(CACHE_PATH):
        return {}

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}

    done = payload.get("done", {}) if isinstance(payload, dict) else {}
    popularity: dict[str, int] = {}

    for course_id, info in done.items():
        if not isinstance(info, dict):
            continue
        total_graded = info.get("total_graded")
        try:
            popularity[str(course_id).upper()] = int(total_graded or 0)
        except Exception:
            popularity[str(course_id).upper()] = 0

    return popularity


class HybridSearcher:
    def __init__(
        self,
        bm25: BM25Index,
        vindex: VectorIndex | None,
        embedder: TextEmbedder | None,
    ):
        self.bm25 = bm25
        self.vindex = vindex
        self.embedder = embedder
        self.popularity = _load_popularity_map()

    @staticmethod
    def _build_search_corpus():
        texts: list[str] = []
        ids: list[str] = []

        with Session(engine) as s:
            for c in s.exec(select(Course)).all():
                geneds_str = (c.geneds or "").replace("|", " ")
                text = f"{c.id} {c.title or ''} {c.description or ''} geneds {geneds_str}"
                texts.append(text.strip())
                ids.append(f"course:{c.id}:0")

            for p in s.exec(select(Professor)).all():
                text = f"{p.name or ''} {p.department or ''} rating {p.avg_rating or ''}"
                texts.append(text.strip())
                ids.append(f"prof:{p.id}:0")

            for r in s.exec(select(Review)).all():
                text = " ".join(
                    part
                    for part in [
                        r.course_id or "",
                        r.professor_id or "",
                        r.review_text or "",
                        r.term or "",
                    ]
                    if part
                )
                if not text:
                    continue
                texts.append(text.strip())
                ids.append(f"review:{r.id}:0")

        return texts, ids

    @staticmethod
    def _nice_course(c: Course):
        title = f"{c.id} - {c.title}".strip(" -")
        desc = _clean(c.description or "")
        return title, (desc[:200] + ("..." if len(desc) > 200 else ""))

    def _course_popularity(self, c: Course) -> int:
        cid = (c.id or "").upper()
        base = cid[:-1] if cid.endswith("H") and len(cid) > 1 else cid
        return int(self.popularity.get(base, 0))

    @classmethod
    def _build_from_db(cls):
        texts, ids = cls._build_search_corpus()
        if not texts:
            texts = [
                "Intro to Java and data structures",
                "Discrete math proofs and logic",
                "Linear algebra for computer science",
            ]
            ids = ["course:CMSC131:0", "course:CMSC250:0", "course:MATH240:0"]

        bm25 = BM25Index(texts, ids)
        bm25.save(BM25_PATH)

        try:
            embedder = TextEmbedder()
            X = embedder.encode(texts)
            vindex = VectorIndex(X.shape[1])
            vindex.add(X, ids)
            vindex.save(FAISS_PATH, FAISS_MAP)
        except Exception:
            embedder = None
            vindex = None

        return cls(bm25, vindex, embedder)

    @classmethod
    def load_or_init(cls):
        init_db()

        try:
            bm25 = BM25Index.load(BM25_PATH) if os.path.exists(BM25_PATH) else None
        except Exception:
            bm25 = None

        try:
            vindex = (
                VectorIndex.load(FAISS_PATH, FAISS_MAP)
                if os.path.exists(FAISS_PATH) and os.path.exists(FAISS_MAP)
                else None
            )
        except Exception:
            vindex = None

        embedder = TextEmbedder() if vindex is not None else None

        if bm25 is not None:
            return cls(bm25, vindex, embedder)

        return cls._build_from_db()

    def _norm(self, d: Dict[str, float]) -> Dict[str, float]:
        if not d:
            return {}
        arr = np.array(list(d.values()), float)
        if arr.max() == arr.min():
            return {k: 0.0 for k in d}
        n = (arr - arr.min()) / (arr.max() - arr.min())
        return {k: float(v) for k, v in zip(d.keys(), n.tolist())}

    def search(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.6,
        dept: str | None = None,
        gened: str | None = None,
        min_credits: int | None = None,
        min_avg_gpa: float | None = None,
        min_ease: float | None = None,
        min_popularity: int | None = None,
        sort_by: str = "relevance",
    ):
        wants_i = wants_i_series(query)
        effective_query = augment_query_with_geneds(query)
        selected_gened = (gened or "").upper().strip() or None

        if not query.strip():
            return self._browse_courses(
                top_k=top_k,
                dept=dept,
                gened=selected_gened,
                min_credits=min_credits,
                min_avg_gpa=min_avg_gpa,
                min_ease=min_ease,
                min_popularity=min_popularity,
                sort_by=sort_by,
            )

        bm25_hits = self.bm25.search(effective_query, top_k=top_k * 10)
        bm25s = {i: s for i, s in bm25_hits}

        vs = {}
        if self.embedder is not None and self.vindex is not None:
            try:
                qvec = self.embedder.encode([effective_query])[0]
                vhits = self.vindex.search(qvec, top_k=top_k * 10)
                vs = {i: s for i, s in vhits}
            except Exception:
                # If the transformer model is unavailable, permanently fall back
                # to BM25 for the rest of this process instead of retrying and
                # stalling every request.
                self.embedder = None
                self.vindex = None
                vs = {}

        keys = set(bm25s) | set(vs)
        if not keys:
            return []

        b = self._norm({k: bm25s.get(k, 0.0) for k in keys})
        v = self._norm({k: vs.get(k, 0.0) for k in keys})
        fused = {
            k: alpha * b.get(k, 0.0) + (1 - alpha) * v.get(k, 0.0)
            for k in keys
        }

        candidate_ids = sorted(
            fused.keys(), key=lambda k: fused[k], reverse=True
        )[: top_k * 10]

        def nice_prof(p: Professor):
            base = p.name or "(Unknown Professor)"
            extra = []
            if p.department:
                extra.append(p.department)
            if p.avg_rating is not None:
                extra.append(f"rating {p.avg_rating:.2f}")
            title = f"{base} - " + ", ".join(extra) if extra else base
            return title, ""

        def nice_review(r: Review):
            text = (r.review_text or "").strip()
            return "Review", (text[:200] + ("..." if len(text) > 200 else ""))

        results = []
        ease_weight = 0.4
        gened_weight = 0.6

        if wants_i:
            with Session(engine) as s:
                courses = s.exec(select(Course)).all()

            for c in courses:
                geneds_tokens = (c.geneds or "").upper().split()
                if "SCIS" not in geneds_tokens:
                    continue
                if dept and not c.id.upper().startswith(dept.upper()):
                    continue
                if selected_gened and selected_gened not in geneds_tokens:
                    continue
                if min_credits is not None and c.credits is not None and c.credits < min_credits:
                    continue
                if min_avg_gpa is not None and (c.avg_gpa is None or c.avg_gpa < min_avg_gpa):
                    continue
                if min_ease is not None and (c.ease_score is None or c.ease_score < min_ease):
                    continue

                popularity = self._course_popularity(c)
                if min_popularity is not None and popularity < min_popularity:
                    continue

                title, snippet = self._nice_course(c)
                gboost = compute_gened_boost(query, c.geneds)
                ease = getattr(c, "ease_score", None) or 0.0
                final_score = 0.6 * gboost + 0.4 * ease

                results.append(
                    {
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
                            "popularity": popularity,
                            "gened_boost": gboost,
                            "course_id": c.id,
                            "description": c.description or "",
                        },
                    }
                )
            return self._finalize_results(
                results,
                top_k=top_k,
                sort_by=sort_by,
                preserve_relevance=True,
            )

        with Session(engine) as s:
            for k in candidate_ids:
                kind, mid, _chunk = k.split(":", 2)
                base_score = float(fused.get(k, 0.0))
                title, snippet, meta = None, None, {}

                if kind == "course":
                    c = s.exec(select(Course).where(Course.id == mid)).first()
                    if not c:
                        continue

                    geneds_tokens = (c.geneds or "").upper().split()
                    if dept and not c.id.upper().startswith(dept.upper()):
                        continue
                    if selected_gened and selected_gened not in geneds_tokens:
                        continue
                    if min_credits is not None and c.credits is not None and c.credits < min_credits:
                        continue
                    if min_avg_gpa is not None and (c.avg_gpa is None or c.avg_gpa < min_avg_gpa):
                        continue
                    if min_ease is not None and (c.ease_score is None or c.ease_score < min_ease):
                        continue

                    popularity = self._course_popularity(c)
                    if min_popularity is not None and popularity < min_popularity:
                        continue

                    gboost = compute_gened_boost(query, c.geneds)
                    ease = getattr(c, "ease_score", None) or 0.0
                    final_score = base_score + ease_weight * ease + gened_weight * gboost

                    title, snippet = self._nice_course(c)
                    meta = {
                        "credits": c.credits,
                        "geneds": c.geneds,
                        "avg_gpa": c.avg_gpa,
                        "ease_score": ease,
                        "popularity": popularity,
                        "pct_ab": getattr(c, "pct_ab", None),
                        "gened_boost": gboost,
                        "course_id": c.id,
                        "description": c.description or "",
                    }

                elif kind == "prof":
                    if selected_gened:
                        continue
                    p = s.exec(select(Professor).where(Professor.id == mid)).first()
                    if not p:
                        continue
                    final_score = base_score
                    title, snippet = nice_prof(p)
                    meta = {"department": p.department, "avg_rating": p.avg_rating}

                elif kind == "review":
                    if selected_gened:
                        continue
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

                else:
                    continue

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

        return self._finalize_results(
            results,
            top_k=top_k,
            sort_by=sort_by,
            preserve_relevance=True,
        )

    def _browse_courses(
        self,
        top_k: int,
        dept: str | None,
        gened: str | None,
        min_credits: int | None,
        min_avg_gpa: float | None,
        min_ease: float | None,
        min_popularity: int | None,
        sort_by: str,
    ):
        results = []
        with Session(engine) as s:
            courses = s.exec(select(Course)).all()

        for c in courses:
            geneds_tokens = (c.geneds or "").upper().split()
            if dept and not c.id.upper().startswith(dept.upper()):
                continue
            if gened and gened not in geneds_tokens:
                continue
            if min_credits is not None and c.credits is not None and c.credits < min_credits:
                continue
            if min_avg_gpa is not None and (c.avg_gpa is None or c.avg_gpa < min_avg_gpa):
                continue
            if min_ease is not None and (c.ease_score is None or c.ease_score < min_ease):
                continue

            popularity = self._course_popularity(c)
            if min_popularity is not None and popularity < min_popularity:
                continue

            title, snippet = self._nice_course(c)
            ease = getattr(c, "ease_score", None) or 0.0

            results.append(
                {
                    "doc_id": f"course:{c.id}:0",
                    "score": 0.0,
                    "kind": "course",
                    "title": title,
                    "snippet": snippet,
                    "meta": {
                        "credits": c.credits,
                        "geneds": c.geneds,
                        "avg_gpa": c.avg_gpa,
                        "ease_score": ease,
                        "popularity": popularity,
                        "pct_ab": getattr(c, "pct_ab", None),
                        "course_id": c.id,
                        "description": c.description or "",
                    },
                }
            )

        return self._finalize_results(
            results,
            top_k=top_k,
            sort_by=sort_by,
            preserve_relevance=False,
        )

    def get_course_detail(self, course_id: str):
        normalized = (course_id or "").strip().upper()
        if not normalized:
            return None

        with Session(engine) as s:
            course = s.get(Course, normalized)
            if not course:
                return None

            reviews = s.exec(
                select(Review).where(Review.course_id == normalized)
            ).all()

            prof_ids = sorted(
                {
                    (review.professor_id or "").strip()
                    for review in reviews
                    if (review.professor_id or "").strip()
                }
            )
            professors = {
                prof.id: prof
                for prof in s.exec(select(Professor).where(Professor.id.in_(prof_ids))).all()
            } if prof_ids else {}

        prof_review_counts: dict[str, int] = {}
        for review in reviews:
            pid = (review.professor_id or "").strip()
            if not pid:
                continue
            prof_review_counts[pid] = prof_review_counts.get(pid, 0) + 1

        professor_summaries = []
        for pid, count in sorted(prof_review_counts.items(), key=lambda item: item[1], reverse=True):
            prof = professors.get(pid)
            professor_summaries.append(
                {
                    "id": pid,
                    "name": prof.name if prof else pid,
                    "avg_rating": prof.avg_rating if prof else None,
                    "review_count": count,
                }
            )

        review_summaries = []
        for review in reviews[:8]:
            pid = (review.professor_id or "").strip() or None
            prof = professors.get(pid) if pid else None
            review_summaries.append(
                {
                    "id": review.id,
                    "professor_id": pid,
                    "professor_name": prof.name if prof else None,
                    "rating": review.rating,
                    "term": review.term,
                    "review_text": review.review_text,
                }
            )

        return {
            "course_id": course.id,
            "title": course.title,
            "description": course.description or "",
            "credits": course.credits,
            "geneds": (course.geneds or "").split(),
            "avg_gpa": course.avg_gpa,
            "ease_score": course.ease_score,
            "pct_ab": getattr(course, "pct_ab", None),
            "popularity": self._course_popularity(course),
            "planetterp_url": f"https://planetterp.com/course/{course.id}",
            "grade_distribution": None,
            "professors": professor_summaries,
            "reviews": review_summaries,
        }

    def _result_sort_key(self, result: dict, sort_by: str):
        meta = result.get("meta") or {}

        if sort_by == "gpa":
            return (float(meta.get("avg_gpa") or -1.0), float(result.get("score", 0.0)))
        if sort_by == "ease":
            return (float(meta.get("ease_score") or -1.0), float(result.get("score", 0.0)))
        if sort_by == "popularity":
            return (float(meta.get("popularity") or -1.0), float(result.get("score", 0.0)))

        return (float(result.get("score", 0.0)), float(meta.get("popularity") or 0.0))

    def _finalize_results(
        self,
        results: list[dict],
        top_k: int,
        sort_by: str,
        preserve_relevance: bool,
    ) -> list[dict]:
        if not results:
            return []

        if preserve_relevance and sort_by != "relevance":
            # Keep metric-based sorting constrained to a strong relevance window
            # so unrelated but popular/easy courses do not swamp the query intent.
            relevant_pool = sorted(
                results,
                key=lambda r: (
                    float(r.get("score", 0.0)),
                    float((r.get("meta") or {}).get("popularity") or 0.0),
                ),
                reverse=True,
            )[: max(top_k * 4, 40)]
            relevant_pool.sort(key=lambda r: self._result_sort_key(r, sort_by), reverse=True)
            return relevant_pool[:top_k]

        results.sort(key=lambda r: self._result_sort_key(r, sort_by), reverse=True)
        return results[:top_k]
