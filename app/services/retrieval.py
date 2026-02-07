import uuid
from functools import lru_cache
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.services.embeddings import embed_texts, get_embedder


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    client = get_qdrant_client()
    embedder = get_embedder()
    dim = embedder.get_sentence_embedding_dimension()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )


def upsert_chunks(chunks: List[str], source: str, tenant_id: str) -> str:
    ensure_collection()
    client = get_qdrant_client()
    vectors = embed_texts(chunks)
    document_id = str(uuid.uuid4())

    points = []
    for idx, (text, vector) in enumerate(zip(chunks, vectors)):
        points.append(
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": text,
                    "source": source,
                    "document_id": document_id,
                    "chunk_index": idx,
                    "tenant_id": tenant_id,
                },
            )
        )

    client.upsert(collection_name=settings.qdrant_collection, points=points)
    return document_id


def search_chunks(query: str, top_k: int, tenant_id: str) -> List[Tuple[str, float, str]]:
    ensure_collection()
    client = get_qdrant_client()
    vector = embed_texts([query])[0]
    tenant_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="tenant_id",
                match=qmodels.MatchValue(value=tenant_id),
            )
        ]
    )
    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        limit=top_k,
        with_payload=True,
        query_filter=tenant_filter,
    )

    matches: List[Tuple[str, float, str]] = []
    for res in results:
        payload = res.payload or {}
        matches.append((payload.get("text", ""), res.score, payload.get("source", "")))
    return matches
