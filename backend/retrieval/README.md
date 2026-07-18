# Retrieval (TA-01/02/03/05)

## Kiáº¿n trÃºc

`backend/retrieval` lÃ  lá»›p in-memory, pure Python, deterministic:

- **TA-01**: BM25 lexical; embedding callable tÃ¹y chá»n vá»›i cosine vÃ  RRF hybrid. KhÃ´ng cÃ³ vector database hay dependency model.
- **TA-02**: `GroundedQAService` truy há»“i context, tráº£ lá»i extractive máº·c Ä‘á»‹nh; LLM chá»‰ Ä‘Æ°á»£c truyá»n vÃ o qua callable.
- **TA-03**: validator/renderer citation fail-closed, kiá»ƒm tra ID, retrieval scope, metadata vÃ  excerpt nguá»“n.
- **TA-05**: golden evaluator Ä‘o Recall@5, citation precision, groundedness, OOS accuracy vÃ  latency.

## Input contract

API nháº­n `intelligence.contracts.NormalizedDocument`, gá»“m `chunks: list[DocumentChunk]` vÃ  citation metadata tÃ¹y chá»n. Má»—i chunk cáº§n `chunk_id`, `page`, `text`; `chunk_id` lÃ  ID upstream, retrieval khÃ´ng táº¡o ID má»›i.

## Public API

```python
from backend.retrieval import (
    GroundedQAService,
    build_index,
    validate_citations,
    render_citations,
)

index = build_index(document, embedding=None)
results = index.search("Kinh phÃ­ láº¥y tá»« Ä‘Ã¢u?", top_k=5)
answer = await GroundedQAService(index).answer("Kinh phÃ­ láº¥y tá»« Ä‘Ã¢u?")

check = validate_citations(
    answer.citation_ids,
    document,
    answer.retrieved_ids,
)
rendered = render_citations(check)
```

`RetrievalResult` giá»¯ nguyÃªn `chunk`, `chunk_id`, `metadata`, `score`, `lexical_score`, `semantic_score`.

`GroundedAnswer` cung cáº¥p `answer`, `citations`, `citation_ids`, `confidence`, `out_of_scope`, `insufficient_evidence`, `latency_ms`; `to_dict()` tráº£ payload serializable.

Citation há»£p lá»‡ pháº£i lÃ  list ID khÃ´ng blank/duplicate/unknown, thuá»™c retrieved chunks, cÃ³ metadata nháº¥t quÃ¡n vÃ  excerpt lÃ  substring Ä‘Ã£ normalize cá»§a chunk nguá»“n. LLM output khÃ´ng Ä‘Æ°á»£c cháº¥p nháº­n náº¿u prose khÃ´ng Ä‘Æ°á»£c cited chunk há»— trá»£; há»‡ thá»‘ng fallback extractive hoáº·c tá»« chá»‘i OOS.

## Golden evaluator

```python
from backend.retrieval import evaluate_golden_set, load_golden_cases

cases = load_golden_cases("tests/fixtures/golden_retrieval.json")
report = evaluate_golden_set(index, cases)
print(report.as_dict())
```

Async code dÃ¹ng `evaluate_golden_set_async`. Case in-scope Ä‘Æ°á»£c cháº¥m retrieval/citation/groundedness; OOS Ä‘Æ°á»£c cháº¥m riÃªng báº±ng `oos_accuracy`.

## Tests

```powershell
python -m pytest tests/test_retrieval.py tests/test_citations.py tests/test_golden_retrieval.py -q
```

## Giá»›i háº¡n vÃ  ownership

- Phá»¥ thuá»™c upstream cung cáº¥p `NormalizedDocument` vÃ  normalized chunks há»£p lá»‡.
- KhÃ´ng táº¡o client LLM/embedding, khÃ´ng gá»i network.
- ChÆ°a tÃ­ch há»£p runtime FastAPI/API/UI.
- TA-04 (trÃ­ch cÄƒn cá»© phÃ¡p lÃ½/Ä‘á»‘i chiáº¿u catalog) deferred.
