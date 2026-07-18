from __future__ import annotations

import os


# Unit and contract tests must be deterministic and must never spend tokens from
# credentials loaded by a developer's local .env. Tests that exercise configured
# LLM behavior inject a fake client or set scoped values explicitly.
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("LLM_MODEL", None)
os.environ.pop("TAVILY_API_KEY", None)
