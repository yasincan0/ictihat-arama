"""Embedding servisi. Uygulama yalnızca Embedder arayüzünü kullanır; model ayarlardan
(EMBEDDING_BACKEND, EMBEDDING_MODEL, EMBEDDING_DIM) seçilir ve değiştirilebilir."""

from __future__ import annotations

import hashlib
import math
import re
import threading
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class Embedder(Protocol):
    dim: int

    def encode_documents(self, texts: list[str]) -> list[list[float]]: ...

    def encode_query(self, text: str) -> list[float]: ...


class EmbeddingConfigError(RuntimeError):
    pass


class SentenceTransformerEmbedder:
    """sentence-transformers ile çok dilli model (varsayılan BAAI/bge-m3). Vektörler normalize
    edilir; benzerlik kosinüs ile ölçülür. E5 ailesi modellerde gereken önekler eklenir."""

    def __init__(self, model_name: str, dim: int, device: str = "cpu") -> None:
        self.model_name = model_name
        self.dim = dim
        self.device = device
        self._model = None
        self._lock = threading.Lock()
        self._e5 = "e5" in model_name.lower()

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    model = SentenceTransformer(self.model_name, device=self.device)
                    actual = (getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension)()
                    if actual != self.dim:
                        raise EmbeddingConfigError(
                            f"{self.model_name} {actual} boyutlu vektör üretiyor; EMBEDDING_DIM={self.dim}. "
                            "Ayarı düzeltip migration'ları yeniden uygulayın."
                        )
                    self._model = model
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, batch_size=16,
                                 show_progress_bar=False, convert_to_numpy=True)
        return [v.tolist() for v in vecs]

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([("passage: " + t) if self._e5 else t for t in texts])

    def encode_query(self, text: str) -> list[float]:
        return self._encode([("query: " + text) if self._e5 else text])[0]


class HashEmbedder:
    """YALNIZCA TEST İÇİN: kelime köklerini boyutlara karma ile dağıtan torba-of-words vektörü.
    Ortak kelime içeren metinleri yakın bulur; anlamsal benzerlik ölçmez."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        low = text.replace("İ", "i").replace("I", "ı").lower()
        for tok in re.findall(r"\w+", low):
            if len(tok) < 3:
                continue
            h = int(hashlib.md5(tok[:5].encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def encode_query(self, text: str) -> list[float]:
        return self._vec(text)


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_backend == "sentence-transformers":
        return SentenceTransformerEmbedder(s.embedding_model, s.embedding_dim, s.embedding_device)
    if s.embedding_backend == "hash":
        return HashEmbedder(s.embedding_dim)
    raise EmbeddingConfigError(f"Bilinmeyen EMBEDDING_BACKEND: {s.embedding_backend}")
