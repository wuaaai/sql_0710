from __future__ import annotations

from typing import Dict, Iterable, List

import requests

from config import EmbeddingConfig


class EmbeddingClient:
    def __init__(self, config: EmbeddingConfig):
        self._config = config
        self._cache: Dict[str, List[float]] = {}

    def embed_many(self, texts: Iterable[str]) -> List[List[float]]:
        payload_texts = list(texts)
        missing = [text for text in payload_texts if text not in self._cache]
        if missing:
            response = requests.post(
                self._config.url,
                headers={"accept": "application/json", "Content-Type": "application/json"},
                json=missing,
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            vectors = data.get("embeddings")
            if not isinstance(vectors, list) or len(vectors) != len(missing):
                raise ValueError("Embedding service returned an unexpected payload.")
            for text, vector in zip(missing, vectors):
                self._cache[text] = vector
        return [self._cache[text] for text in payload_texts]

    def embed_one(self, text: str) -> List[float]:
        return self.embed_many([text])[0]
