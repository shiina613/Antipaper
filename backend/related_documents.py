"""Grounded extraction and allowlisted Tavily enrichment for related documents."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from .intelligence import NormalizedDocument
from .schemas import RelatedDocument


DEFAULT_ALLOWED_DOMAINS = ("gov.vn", "vnexpress.net")
DEFAULT_TAVILY_BASE_URL = "https://api.tavily.com"
_DOCUMENT_NUMBER = re.compile(
    r"\b\d{1,4}(?:/\d{4})?/[A-ZĐ0-9-]{2,}(?:/[A-ZĐ0-9-]{2,})?\b",
    flags=re.IGNORECASE,
)
_DOCUMENT_TYPE = (
    r"Bộ\s+luật|Luật|Pháp\s+lệnh|Nghị\s+định|Nghị\s+quyết|"
    r"Thông\s+tư(?:\s+liên\s+tịch)?|Quyết\s+định|Chỉ\s+thị|"
    r"Kế\s+hoạch|Đề\s+án|Công\s+văn"
)
_PAREN_REFERENCE = re.compile(
    rf"(?P<title>\b(?:{_DOCUMENT_TYPE})\b[^.;\n()]{{2,100}}?)\s*"
    rf"\((?P<number>{_DOCUMENT_NUMBER.pattern})\)",
    flags=re.IGNORECASE,
)
_NUMBERED_REFERENCE = re.compile(
    rf"(?P<title>\b(?:{_DOCUMENT_TYPE})\b\s*(?:số\s*)?"
    rf"(?P<number>{_DOCUMENT_NUMBER.pattern})(?:\s+[^.;\n()]{{0,80}})?)",
    flags=re.IGNORECASE,
)
_NAMED_LAW = re.compile(
    r"(?P<title>\b(?:Bộ\s+luật|Luật)\s+[A-ZÀ-ỴĐ][^.;\n()] {2,80})",
    flags=re.VERBOSE,
)


@dataclass(frozen=True)
class RelatedDocumentMention:
    title: str
    document_number: str
    citation_id: str
    page: int
    context: str


@dataclass(frozen=True)
class TavilyResult:
    title: str
    url: str
    content: str
    score: float


class TavilySearchClient:
    """Minimal Tavily Search API client with defense-in-depth domain filtering."""

    def __init__(
        self,
        *,
        api_key: str,
        allowed_domains: Iterable[str] = DEFAULT_ALLOWED_DOMAINS,
        base_url: str = DEFAULT_TAVILY_BASE_URL,
        timeout_seconds: float = 8.0,
        max_results: int = 5,
    ) -> None:
        self.api_key = api_key.strip()
        self.allowed_domains = tuple(
            domain.strip().casefold().lstrip(".")
            for domain in allowed_domains
            if domain.strip()
        )
        self.base_url = base_url.rstrip("/") or DEFAULT_TAVILY_BASE_URL
        self.timeout_seconds = max(1.0, min(timeout_seconds, 20.0))
        self.max_results = max(1, min(max_results, 20))

    @classmethod
    def from_env(cls) -> "TavilySearchClient | None":
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key:
            return None
        domains = tuple(
            item.strip()
            for item in os.getenv(
                "TAVILY_ALLOWED_DOMAINS",
                ",".join(DEFAULT_ALLOWED_DOMAINS),
            ).split(",")
            if item.strip()
        )
        return cls(
            api_key=api_key,
            allowed_domains=domains,
            base_url=os.getenv("TAVILY_BASE_URL", "").strip() or DEFAULT_TAVILY_BASE_URL,
            timeout_seconds=float(os.getenv("TAVILY_TIMEOUT_SECONDS", "8")),
            max_results=int(os.getenv("TAVILY_MAX_RESULTS", "5")),
        )

    def search(self, query: str) -> list[TavilyResult]:
        payload = {
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": self.max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_domains": list(self.allowed_domains),
            "country": "vietnam",
            "safe_search": True,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/search",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            values = response.json().get("results", [])
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return []

        results: list[TavilyResult] = []
        for value in values:
            url = str(value.get("url") or "").strip()
            if not self.is_allowed_url(url):
                continue
            results.append(
                TavilyResult(
                    title=str(value.get("title") or "").strip(),
                    url=url,
                    content=str(value.get("content") or "").strip(),
                    score=float(value.get("score") or 0.0),
                )
            )
        return results

    def is_allowed_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").casefold().rstrip(".")
        except ValueError:
            return False
        if parsed.scheme not in {"http", "https"} or not hostname:
            return False
        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.allowed_domains
        )


class RelatedDocumentFinder:
    """Extract explicit legal references and optionally enrich them with Tavily."""

    def __init__(
        self,
        search_client: TavilySearchClient | None = None,
        *,
        max_references: int = 8,
    ) -> None:
        self.search_client = search_client
        self.max_references = max(1, min(max_references, 20))

    @classmethod
    def from_env(cls) -> "RelatedDocumentFinder":
        return cls(
            TavilySearchClient.from_env(),
            max_references=int(os.getenv("RELATED_DOCUMENT_MAX_REFERENCES", "8")),
        )

    def find(self, document: NormalizedDocument) -> list[RelatedDocument]:
        mentions = self.extract_mentions(document)[: self.max_references]
        return [self._resolve(mention) for mention in mentions]

    def extract_mentions(
        self,
        document: NormalizedDocument,
    ) -> list[RelatedDocumentMention]:
        mentions: list[RelatedDocumentMention] = []
        seen: set[str] = set()
        seen_titles: set[str] = set()
        for chunk in document.chunks:
            matches: list[tuple[str, str]] = []
            for pattern in (_PAREN_REFERENCE, _NUMBERED_REFERENCE):
                for match in pattern.finditer(chunk.text):
                    matches.append((match.group("title"), match.group("number")))
            for match in _NAMED_LAW.finditer(chunk.text):
                title = match.group("title")
                number_match = _DOCUMENT_NUMBER.search(title)
                matches.append((title, number_match.group(0) if number_match else ""))

            for raw_title, raw_number in matches:
                title = self._clean_title(raw_title, raw_number)
                number = raw_number.strip(" .,:;()")
                key = self._normalize_key(number or title)
                title_key = self._normalize_key(title)
                if (
                    not title
                    or key in seen
                    or (not number and title_key in seen_titles)
                ):
                    continue
                seen.add(key)
                seen_titles.add(title_key)
                mentions.append(
                    RelatedDocumentMention(
                        title=title,
                        document_number=number,
                        citation_id=chunk.chunk_id,
                        page=chunk.page,
                        context=self._shorten(chunk.text, 700),
                    )
                )
        return mentions

    def _resolve(self, mention: RelatedDocumentMention) -> RelatedDocument:
        result = self._search_result(mention)
        if result is None:
            return RelatedDocument(
                title=mention.title,
                document_number=mention.document_number,
                mentioned_name=mention.title,
                source="cited_in_document",
                reason=(
                    f"Tài liệu nhắc trực tiếp căn cứ này tại trang {mention.page}; "
                    "chưa có nguồn web phù hợp trong allowlist để đối chiếu."
                ),
                citation_ids=[mention.citation_id],
                excerpt=mention.context,
            )

        hostname = (urlparse(result.url).hostname or "").casefold()
        return RelatedDocument(
            title=mention.title,
            document_number=mention.document_number,
            mentioned_name=mention.title,
            source="tavily",
            reason=(
                f"Tài liệu nhắc trực tiếp căn cứ này tại trang {mention.page}; "
                f"kết quả từ {hostname} được dùng để đối chiếu nội dung liên quan."
            ),
            citation_ids=[mention.citation_id],
            url=result.url,
            publisher=hostname,
            excerpt=self._shorten(result.content or mention.context, 900),
        )

    def _search_result(self, mention: RelatedDocumentMention) -> TavilyResult | None:
        if self.search_client is None:
            return None
        target = " ".join(
            part for part in (mention.title, mention.document_number) if part
        )
        results = self.search_client.search(f'"{target}" văn bản quy định chính thức')
        for result in sorted(results, key=lambda item: item.score, reverse=True):
            if self._is_relevant(mention, result):
                return result
        return None

    @classmethod
    def _is_relevant(
        cls,
        mention: RelatedDocumentMention,
        result: TavilyResult,
    ) -> bool:
        haystack = cls._normalize_key(f"{result.title} {result.content} {result.url}")
        if mention.document_number:
            number = cls._normalize_key(mention.document_number)
            if number and number in haystack:
                return True
        title_tokens = {
            token
            for token in cls._normalize_key(mention.title).split()
            if len(token) >= 4
        }
        return len(title_tokens.intersection(haystack.split())) >= min(2, len(title_tokens))

    @staticmethod
    def _clean_title(title: str, number: str) -> str:
        compact = re.sub(r"\s+", " ", title).strip(" .,:;()")
        if number:
            compact = re.sub(re.escape(number), "", compact, flags=re.IGNORECASE)
            compact = re.sub(r"\bsố\s*$", "", compact, flags=re.IGNORECASE)
        return compact.strip(" .,:;()")

    @staticmethod
    def _normalize_key(value: str) -> str:
        return " ".join(re.findall(r"[\wÀ-ỹ/-]+", value.casefold()))

    @staticmethod
    def _shorten(value: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", value).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."
