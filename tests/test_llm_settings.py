import pytest
from pydantic import BaseModel

from src.integrations.llm import LlmClient, LlmClientOutputError, LlmSettings


def test_full_chat_completions_base_url_is_not_doubled(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1/chat/completions")
    monkeypatch.delenv("LLM_API_URL", raising=False)

    assert LlmSettings.from_env().api_url == "https://api.openai.com/v1/chat/completions"


def test_base_url_receives_chat_completions_suffix(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("LLM_API_URL", raising=False)

    assert LlmSettings.from_env().api_url == "https://api.openai.com/v1/chat/completions"


class _ResponseModel(BaseModel):
    answer: str


def test_structured_response_accepts_fenced_json_from_compatible_provider() -> None:
    response = {
        "choices": [{"finish_reason": "stop", "message": {"content": "```json\n{\"answer\": \"ok\"}\n```"}}]
    }

    assert LlmClient._validate_response(response, _ResponseModel).answer == "ok"


def test_structured_response_detects_truncation_before_json_validation() -> None:
    response = {"choices": [{"finish_reason": "length", "message": {"content": "{\"answer\":"}}]}

    with pytest.raises(LlmClientOutputError, match="truncated"):
        LlmClient._validate_response(response, _ResponseModel)
