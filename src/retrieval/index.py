"""Deterministic in-memory lexical, semantic, and hybrid retrieval."""
from __future__ import annotations

import math
import re
import inspect
from types import MappingProxyType
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Sequence

try:
    from intelligence.contracts import DocumentChunk, NormalizedDocument, coerce_normalized_document
except ModuleNotFoundError:
    from src.intelligence.contracts import DocumentChunk, NormalizedDocument, coerce_normalized_document

_TOKEN = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {"là", "và", "của", "cho", "có", "được", "từ", "nào", "gì", "bao", "nhiêu", "ai", "những", "các", "một", "trong", "về", "khi", "này", "đó", "thế"}


def _tokens(value: str) -> list[str]:
    return _TOKEN.findall(value.casefold())


def meaningful_tokens(value: str) -> set[str]:
    return {token for token in _tokens(value) if token not in STOPWORDS and len(token) > 1}


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
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
    def __init__(self, document: NormalizedDocument, embedding: Callable[[str], Any] | None = None, vectors: Mapping[str, Sequence[float]] | None = None, lexical_reservation_threshold: float = 0.5):
        self.document = coerce_normalized_document(document).model_copy(deep=True)
        self.chunks = tuple(self.document.chunks)
        self.embedding = embedding
        if not 0.0 <= lexical_reservation_threshold <= 1.0:
            raise ValueError("lexical reservation threshold must be between 0 and 1")
        self.lexical_reservation_threshold = lexical_reservation_threshold
        self._terms = [_tokens(c.text) for c in self.chunks]
        self._lengths = [len(t) for t in self._terms]
        self._average_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        if vectors is not None:
            # Explicit caches are configuration input: fail closed loudly.
            self._vectors = MappingProxyType(self._validate_vectors(vectors))
            prepared = None
        elif embedding is not None:
            try:
                prepared = {chunk.chunk_id: embedding(chunk.text) for chunk in self.chunks}
                self._vectors = MappingProxyType(self._validate_vectors(prepared))
            except Exception:
                prepared = None
                self._vectors = MappingProxyType({})
        else:
            prepared = None
            self._vectors = MappingProxyType({})

    def _validate_vectors(self, vectors: Mapping[str, Sequence[float]]) -> dict[str, tuple[float, ...]]:
        if not isinstance(vectors, Mapping) or set(vectors) != {chunk.chunk_id for chunk in self.chunks}:
            raise ValueError("vectors must map every chunk_id exactly")
        converted: dict[str, tuple[float, ...]] = {}
        dimensions: int | None = None
        for chunk in self.chunks:
            raw = vectors[chunk.chunk_id]
            if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
                raise ValueError("embedding vector must be a numeric sequence")
            if any(isinstance(value, bool) for value in raw):
                raise ValueError("embedding vectors cannot contain boolean values")
            vector = tuple(float(value) for value in raw)
            if not vector or any(not math.isfinite(value) for value in vector):
                raise ValueError("embedding vectors must be finite and non-empty")
            dimensions = dimensions or len(vector)
            if len(vector) != dimensions:
                raise ValueError("embedding vectors must have consistent dimensions")
            converted[chunk.chunk_id] = vector
        return converted

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

    def search(self, question: str, top_k: int = 5, _query_vector: Sequence[float] | None = None, _semantic_enabled: bool | None = None) -> list[RetrievalResult]:
        if top_k <= 0 or not self.chunks:
            return []
        lexical = self._bm25(question)
        semantic = [0.0] * len(self.chunks)
        vectors = self._vectors
        semantic_available = bool(vectors) and (_query_vector is not None or (self.embedding is not None and _semantic_enabled is not False))
        if semantic_available:
            try:
                embed = self.embedding
                query_vector = list(_query_vector) if _query_vector is not None else list(map(float, embed(question))) if embed is not None else []
                semantic = [_cosine(query_vector, vectors.get(chunk.chunk_id, ())) for chunk in self.chunks]
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
            semantic_order = semantic_order[:50]
            semantic_rank = {i: rank for rank, i in enumerate(semantic_order)}
            eligible = set(lexical_order) | set(semantic_order)
            rrf = {i: (1 / (60 + lexical_rank[i] + 1) if i in lexical_rank else 0) + (1 / (60 + semantic_rank[i] + 1) if i in semantic_rank else 0) for i in eligible}
            order = sorted(eligible, key=lambda i: (-rrf[i], self.chunks[i].chunk_id))
            scores = rrf
        else:
            order = list(lexical_order)
            scores = {i: lexical[i] for i in range(len(self.chunks))}
        if lexical_order and lexical[lexical_order[0]] > 0:
            query_terms = meaningful_tokens(question)
            chunk_terms = meaningful_tokens(self.chunks[lexical_order[0]].text)
            coverage = len(query_terms & chunk_terms) / max(1, len(query_terms))
            if coverage >= self.lexical_reservation_threshold and lexical_order[0] in order:
                order.remove(lexical_order[0])
                order = [lexical_order[0], *order]
        return [RetrievalResult(self.chunks[i], scores[i], lexical[i], semantic[i]) for i in order[:top_k]]

    async def asearch(self, question: str, query_embedder: Callable[[list[str]], Awaitable[Any]] | None = None, top_k: int = 5) -> list[RetrievalResult]:
        if not self._vectors or query_embedder is None:
            return self._search_with_semantic(question, top_k, None)
        try:
            vector = query_embedder([question])
            if inspect.isawaitable(vector):
                vector = await vector
            if not isinstance(vector, list) or len(vector) != 1 or not isinstance(vector[0], list):
                raise ValueError("query embedder must return one vector in list-of-lists form")
            raw_query_vector = vector[0]
            if not raw_query_vector or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in raw_query_vector):
                raise ValueError("invalid query vector")
            query_vector = [float(value) for value in raw_query_vector]
            dimensions = {len(item) for item in self._vectors.values()}
            if len(dimensions) != 1 or len(query_vector) != next(iter(dimensions)):
                raise ValueError("invalid query vector")
            return self._search_with_semantic(question, top_k, query_vector)
        except Exception:
            return self._search_with_semantic(question, top_k, None)

    def _search_with_semantic(self, question: str, top_k: int, query_vector: Sequence[float] | None) -> list[RetrievalResult]:
        if query_vector is None:
            return self.search(question, top_k, _semantic_enabled=False)
        return self.search(question, top_k, _query_vector=query_vector)


def build_index(document: NormalizedDocument, embedding: Callable[[str], Any] | None = None, vectors: Mapping[str, Sequence[float]] | None = None, lexical_reservation_threshold: float = 0.5) -> RetrievalIndex:
    return RetrievalIndex(document, embedding=embedding, vectors=vectors, lexical_reservation_threshold=lexical_reservation_threshold)


async def build_index_async(document: NormalizedDocument, embedder: Callable[[list[str]], Awaitable[Sequence[Sequence[float]]]], batch_size: int = 64, lexical_reservation_threshold: float = 0.5) -> RetrievalIndex:
    normalized = coerce_normalized_document(document)
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    keyed: dict[str, Sequence[float]] = {}
    for start in range(0, len(normalized.chunks), batch_size):
        batch = normalized.chunks[start : start + batch_size]
        vectors = await embedder([chunk.text for chunk in batch])
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise ValueError("document embedding count mismatch")
        keyed.update({chunk.chunk_id: vector for chunk, vector in zip(batch, vectors)})
    return RetrievalIndex(normalized, vectors=keyed, lexical_reservation_threshold=lexical_reservation_threshold)
