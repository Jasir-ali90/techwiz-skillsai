"""Local sentence embeddings (all-MiniLM-L6-v2, 384 dimensions).

A numeric similarity model, not a generative one: it is safe for the
validation layer to use. If the model changes, EMBEDDING_DIM and the
Vector(...) column must change with it.
"""
from functools import lru_cache

from src.core.config import get_settings

EMBEDDING_DIM = 384
BATCH_SIZE = 32


@lru_cache
def get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = get_model().encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]


def warm() -> None:
    embed_one("warm up")
