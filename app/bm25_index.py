import pickle
from rank_bm25 import BM25Okapi
from typing import List, Tuple
ARTIFACT = 'data/artifacts/bm25.pkl'

def _tok(s: str) -> List[str]:
    return [t.lower() for t in s.split()]

class BM25Index:
    def __init__(self, documents: List[str], doc_ids: List[str]):
        self.doc_ids = doc_ids
        self.bm25 = BM25Okapi([_tok(d) for d in documents])
    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        scores = self.bm25.get_scores(_tok(query))
        pairs = list(zip(self.doc_ids, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:top_k]
    def save(self, path: str = ARTIFACT):
        with open(path, 'wb') as f:
            pickle.dump({'doc_ids': self.doc_ids, 'bm25': self.bm25}, f)
    @classmethod
    def load(cls, path: str = ARTIFACT):
        with open(path, 'rb') as f:
            obj = pickle.load(f)
        inst = object.__new__(cls); inst.doc_ids = obj['doc_ids']; inst.bm25 = obj['bm25']; return inst
