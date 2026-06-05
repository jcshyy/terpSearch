from app.search_service import HybridSearcher

def test_search_smoke():
    s = HybridSearcher.load_or_init()
    # Keep the smoke test fast and deterministic by avoiding model load/download.
    s.embedder = None
    s.vindex = None
    res = s.search('discrete math proofs', top_k=5)
    assert isinstance(res, list) and len(res) > 0 and 'doc_id' in res[0]
