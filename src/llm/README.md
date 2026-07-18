# Shared LLM client

`LlmClient.embed(texts)` provides independent OpenAI-compatible embeddings.
It uses `EMBEDDING_API_URL` directly (default
`https://api.openai.com/v1/embeddings`) and `EMBEDDING_MODEL` (default
`text-embedding-3-small`); it never derives embedding URLs from chat settings.

Embedding responses are reordered by `index` and fail closed on count, index,
dimension, non-finite-value, batch, or text-bound violations. Empty input
returns without network activity. `OPENAI_API_KEY` takes precedence over
`LLM_API_KEY`; never commit either key.

For multiple event loops, create one process limiter and inject it into a
separate client per loop. Never share an injected `httpx.AsyncClient` across
loops:

```python
from llm import LlmClient, LlmSettings, shared_limiter

limiter = shared_limiter(5)
client = LlmClient(LlmSettings(api_url="...", max_concurrency=5), limiter=limiter)
```
