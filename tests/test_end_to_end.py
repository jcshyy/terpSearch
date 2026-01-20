from app.search_service import HybridSearcher

def test_search_smoke():
    s = HybridSearcher.load_or_init()
    res = s.search('discrete math proofs', top_k=5)
    assert isinstance(res, list) and len(res) > 0 and 'doc_id' in res[0]
