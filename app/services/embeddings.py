from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

from app.core.config import settings


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: List[str]) -> List[List[float]]:
    embedder = get_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
