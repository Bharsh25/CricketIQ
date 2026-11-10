
_model = None
_col = None

def _get():
    global _model, _col
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    if _col is None:
        import chromadb
        client = chromadb.PersistentClient(path="data/chroma")
        _col = client.get_collection("cricket_docs")
    return _model, _col

def search_cricket_docs(query: str, k: int = 4, doc_type: str | None = None) -> dict:
    """Search match summaries and the cricket glossary."""
    try:
        model, col = _get()
    except Exception as e:
        return {"error": f"Knowledge index unavailable: {str(e)[:100]}"}
    emb = model.encode([query], normalize_embeddings=True).tolist()
    where = {"type": doc_type} if doc_type else None
    res = col.query(query_embeddings=emb, n_results=k, where=where)
    return {"results": res["documents"][0]}