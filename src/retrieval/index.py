"""Deterministic in-memory lexical, semantic, and hybrid retrieval."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from intelligence.contracts import DocumentChunk, NormalizedDocument, coerce_normalized_document

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return _TOKEN.findall(value.casefold())


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left or not any(left) or not any(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    denom = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    value = dot / denom if denom else 0.0
    return value if math.isfinite(value) else 0.0


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    @property
    def metadata(self) -> dict[str, Any]:
        return self.chunk.model_dump(exclude={"text", "chunk_id"})


class RetrievalIndex:
    def __init__(self, document: NormalizedDocument, embedding: Callable[[str], Any] | None = None):
        self.document = coerce_normalized_document(document)
        self.chunks = tuple(self.document.chunks)
        self.embedding = embedding
        self._terms = [_tokens(c.text) for c in self.chunks]
        self._lengths = [len(t) for t in self._terms]
        self._average_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        self._vectors: list[list[float] | None] = []
        if embedding is not None:
            try:
                embed = embedding
                vectors = [list(map(float, embed(c.text))) for c in self.chunks]
                dimension = len(vectors[0]) if vectors else 0
                if dimension and all(len(vector) == dimension and vector and all(math.isfinite(v) for v in vector) for vector in vectors):
                    self._vectors = vectors  # type: ignore[assignment]
            except Exception:
                self._vectors = []

    def _bm25(self, question: str) -> list[float]:
        query = _tokens(question)
        if not query or not self.chunks:
            return [0.0] * len(self.chunks)
        n = len(self.chunks)
        document_frequency = {term: sum(term in terms for terms in self._terms) for term in set(query)}
        scores = []
        for terms, length in zip(self._terms, self._lengths):
            counts = {term: terms.count(term) for term in set(query)}
            score = 0.0
            for term, frequency in counts.items():
                if not frequency:
                    continue
                idf = math.log(1 + (n - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * length / self._average_length) if self._average_length else 1
                score += idf * frequency * 2.5 / denominator
            scores.append(score)
        return scores

    def search(self, question: str, top_k: int = 5) -> list[RetrievalResult]:
        if top_k <= 0 or not self.chunks:
            return []
        lexical = self._bm25(question)
        semantic = [0.0] * len(self.chunks)
        semantic_available = bool(self._vectors) and self.embedding is not None
        if semantic_available:
            try:
                embed = self.embedding
                query_vector = list(map(float, embed(question))) if embed is not None else []
                semantic = [_cosine(query_vector, vector or []) for vector in self._vectors]
            except Exception:
                semantic_available = False
        lexical_candidates = [i for i, score in enumerate(lexical) if score > 0 and math.isfinite(score)]
        lexical_order = sorted(lexical_candidates, key=lambda i: (-lexical[i], self.chunks[i].chunk_id))
        semantic_candidates = [i for i, score in enumerate(semantic) if score > 0 and math.isfinite(score)]
        semantic_order = sorted(semantic_candidates, key=lambda i: (-semantic[i], self.chunks[i].chunk_id))
        if semantic_available:
            # Reciprocal rank fusion keeps both independent signals deterministic.
            lexical_rank = {i: rank for rank, i in enumerate(lexical_order)}
            semantic_rank = {i: rank for rank, i in enumerate(semantic_order)}
            eligible = set(lexical_order) | set(semantic_order)
            rrf = {i: (1 / (60 + lexical_rank[i] + 1) if i in lexical_rank else 0) + (1 / (60 + semantic_rank[i] + 1) if i in semantic_rank else 0) for i in eligible}
            order = sorted(eligible, key=lambda i: (-rrf[i], self.chunks[i].chunk_id))
            scores = rrf
        else:
            order = lexical_order
            scores = {i: lexical[i] for i in range(len(self.chunks))}
        return [RetrievalResult(self.chunks[i], scores[i], lexical[i], semantic[i]) for i in order[:top_k]]


def build_index(document: NormalizedDocument, embedding: Callable[[str], Any] | None = None) -> RetrievalIndex:
    return RetrievalIndex(document, embedding=embedding)
