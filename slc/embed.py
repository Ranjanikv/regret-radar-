"""Lightweight multilingual sentence embedding model inside Exasol Python SLC."""

from sentence_transformers import SentenceTransformer

# Load a lightweight multilingual sentence embedding model (all-MiniLM-L6-v2)
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    """Return a dense vector for *text* as a plain Python list."""
    if not text:
        return []
    vector = _model.encode([text])[0]
    return vector.tolist()
