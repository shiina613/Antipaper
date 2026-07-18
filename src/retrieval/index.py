"""Deterministic in-memory lexical retrieval."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..intelligence.contracts import DocumentChunk, NormalizedDocument


def _tokens(value: str) -> list[str]:
    return re.findall(r"[\wÀ-ỹĐđ]+", value.casefold())


def meaningful_tokens(value: str) -> set[str]:
    return {token for token in _tokens(value) if len(token) > 1}


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    score: float
    lexical_score: float

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    @property
    def metadata(self) -> dict[str, object]:
        return {"page": self.chunk.page, "chunk_id": self.chunk_id}


class RetrievalIndex:
    def __init__(self, document: NormalizedDocument) -> None:
        self.document = document
        self.chunks = tuple(document.chunks)
        self._tokens = [meaningful_tokens(chunk.text) for chunk in self.chunks]
        self._document_frequency = {
            token: sum(token in chunk_tokens for chunk_tokens in self._tokens)
            for chunk_tokens in self._tokens for token in chunk_tokens
        }

    def search(self, question: str, top_k: int = 5) -> list[RetrievalResult]:
        query = meaningful_tokens(question)
        if not query:
            return []
        total = max(len(self.chunks), 1)
        results: list[RetrievalResult] = []
        for chunk, tokens in zip(self.chunks, self._tokens):
            overlap = query & tokens
            if not overlap:
                continue
            score = sum(math.log((total + 1) / (self._document_frequency[token] + 0.5)) + 1 for token in overlap)
            score /= math.sqrt(max(len(tokens), 1))
            results.append(RetrievalResult(chunk, score, score))
        return sorted(results, key=lambda item: (-item.score, item.chunk.page, item.chunk_id))[:top_k]

    async def asearch(self, question: str, _unused: object = None, top_k: int = 5) -> list[RetrievalResult]:
        return self.search(question, top_k)


def build_index(document: NormalizedDocument, **_: object) -> RetrievalIndex:
    return RetrievalIndex(document)


async def build_index_async(document: NormalizedDocument, *_: object, **__: object) -> RetrievalIndex:
    return RetrievalIndex(document)
