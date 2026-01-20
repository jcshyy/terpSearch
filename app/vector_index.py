import pickle, faiss, numpy as np
from typing import List, Tuple
ARTIFACT = 'data/artifacts/faiss.index'
MAP_PATH = 'data/artifacts/faiss_ids.pkl'
class VectorIndex:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatIP(dim)
        self.ids: List[str] = []
    def add(self, X: np.ndarray, ids: List[str]):
        self.index.add(X.astype(np.float32)); self.ids.extend(ids)
    def search(self, qvec: np.ndarray, top_k: int = 20) -> List[Tuple[str, float]]:
        if qvec.ndim == 1: qvec = qvec[None, :]
        D, I = self.index.search(qvec.astype(np.float32), top_k)
        return [(self.ids[i], float(D[0][j])) for j,i in enumerate(I[0]) if i != -1]
    def save(self, path: str = ARTIFACT, map_path: str = MAP_PATH):
        faiss.write_index(self.index, path); pickle.dump(self.ids, open(map_path, 'wb'))
    @classmethod
    def load(cls, path: str = ARTIFACT, map_path: str = MAP_PATH):
        inst = object.__new__(cls); inst.index = faiss.read_index(path); inst.ids = pickle.load(open(map_path,'rb')); return inst
