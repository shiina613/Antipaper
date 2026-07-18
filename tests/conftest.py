from __future__ import annotations

import os


# Unit and contract tests must be deterministic and must never spend tokens from
# credentials loaded by a developer's local .env. Tests that exercise configured
# LLM behavior inject a fake client or set scoped values explicitly.
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = "gpt-4o-mini"
os.environ["EMBEDDING_MODEL"] = "text-embedding-3-small"
os.environ["TAVILY_API_KEY"] = ""
