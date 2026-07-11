"""向量化服务调用模块。"""

from __future__ import annotations

from typing import Dict, List

import requests

from config import EmbeddingConfig


class EmbeddingClient:
    """负责调用 embedding 服务，并缓存已算过的文本向量。"""

    def __init__(self, config: EmbeddingConfig):
        """初始化向量服务配置和本地缓存。"""
        self._config = config
        self._cache: Dict[str, List[float]] = {}

    def embed_one(self, text: str) -> List[float]:
        """把单条文本转成一个向量。"""
        return self.embed_many([text])[0]

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """批量把多条文本转成向量。"""
        missing = [text for text in texts if text not in self._cache]
        if missing:
            response = requests.post(
                self._config.url,
                headers={"accept": "application/json", "Content-Type": "application/json"},
                json=missing,
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            vectors = payload.get("embeddings", [])
            if len(vectors) != len(missing):
                raise ValueError("Embedding service returned an unexpected number of vectors.")
            for text, vector in zip(missing, vectors):
                self._cache[text] = vector
        return [self._cache[text] for text in texts]
