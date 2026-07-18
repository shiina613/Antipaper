"""Versioned release-dataset contracts shared by deterministic and LLM evals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RecordType = Literal["qa", "summary", "term", "suggested_question"]


class ReleaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    record_type: RecordType
    id: str = Field(min_length=1)
    expected_output: str = Field(min_length=1)
    gold_citation_ids: list[str] = Field(default_factory=list)
    document_path: str = Field(min_length=1)
    question: str | None = None
    scope: Literal["in", "out"] | None = None
    expected_answer_points: list[str] = Field(default_factory=list)
    expected_out_of_scope: bool | None = None
    category: str | None = None
    difficulty: Literal["easy", "medium", "hard"] | None = None
    section: Literal["context", "main_content", "decision_points", "impact"] | None = None
    term: str | None = None

    @model_validator(mode="after")
    def validate_record_shape(self) -> "ReleaseRecord":
        if self.record_type == "qa":
            if not self.question or self.scope is None or self.expected_out_of_scope is None:
                raise ValueError("qa records require question, scope, and expected_out_of_scope")
            if self.scope == "in" and not self.gold_citation_ids:
                raise ValueError("in-scope qa records require gold citations")
            if self.scope == "out" and self.gold_citation_ids:
                raise ValueError("out-of-scope qa records cannot have gold citations")
        elif self.record_type == "summary" and self.section is None:
            raise ValueError("summary records require section")
        elif self.record_type == "term" and not self.term:
            raise ValueError("term records require term")
        return self


def load_release_records(path: str | Path) -> list[ReleaseRecord]:
    source = Path(path)
    records = [
        ReleaseRecord.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    identifiers = [record.id for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("release dataset record IDs must be unique")
    return records

