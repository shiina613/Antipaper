from pathlib import Path
import time

import pytest

from src.errors import ApiError
from src.ingestion import DocumentIngestor
from src.integrations.llm import LlmClientOutputError, LlmClientTimeoutError
from src.retrieval import build_index
from src.services.documents import AntipaperService
from src.services.orchestrator import DocumentOrchestrator


SAMPLE = Path("data/quyet_dinh.pdf")


def test_native_ingestion_and_lexical_retrieval() -> None:
    document, pages = DocumentIngestor().ingest_bytes(
        file_name="quyet_dinh.pdf", file_bytes=SAMPLE.read_bytes(), document_id="test-document"
    )
    assert pages and document.chunks
    assert build_index(document).search(document.chunks[0].text[:80])


def test_missing_llm_configuration_returns_grounded_partial_report(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = AntipaperService(history_path=tmp_path / "history.sqlite3")
    service.store._related_document_finder = None
    data = SAMPLE.read_bytes()
    first = service.submit_document("quyet_dinh.pdf", data, user_id="test")
    second = service.submit_document("quyet_dinh.pdf", data, user_id="test")
    for _ in range(100):
        if all(service.get_status(item.document_id).status == "completed" for item in (first, second)):
            break
        time.sleep(0.01)
    assert first.document_id != second.document_id
    assert "cached" not in first.model_dump()
    first_status = service.get_status(first.document_id)
    second_status = service.get_status(second.document_id)
    assert first_status.status == "completed"
    assert second_status.status == "completed"
    report = service.get_report(first.document_id)
    assert report.generation_mode == "terminology_partial"
    assert report.quality.report_status == "partial"
    assert "LLM_NOT_CONFIGURED" in report.quality.terminology.warnings
    assert service.list_history(user_id="test").total == 2
    service.shutdown()


def test_llm_timeout_marks_document_task_failed(tmp_path: Path) -> None:
    class TimeoutOrchestrator:
        llm_enabled = True

        def process(self, **_kwargs):  # noqa: ANN003
            raise LlmClientTimeoutError("LLM request timed out.")

    service = AntipaperService(history_path=tmp_path / "history.sqlite3")
    service.store._related_document_finder = None
    service.store._orchestrator = TimeoutOrchestrator()
    upload = service.submit_document("quyet_dinh.pdf", SAMPLE.read_bytes(), user_id="test")

    for _ in range(100):
        status = service.get_status(upload.document_id)
        if status.status == "failed":
            break
        time.sleep(0.01)

    assert status.error and status.error.code == "MODEL_TIMEOUT"
    service.shutdown()


def test_invalid_llm_schema_returns_deterministic_partial_report() -> None:
    class InvalidSchemaLlm:
        async def call(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            raise LlmClientOutputError("LLM response is not valid JSON matching the requested schema.")

    report = DocumentOrchestrator(llm=InvalidSchemaLlm()).process(
        document_id="schema-fallback",
        file_name="quyet_dinh.pdf",
        file_bytes=SAMPLE.read_bytes(),
    ).report

    assert report.generation_mode == "terminology_partial"
    assert report.quality.report_status == "partial"
    assert "LLM_GENERATION_FAILED" in report.quality.terminology.warnings
    assert report.summary.context


def test_history_survives_but_active_report_does_not(tmp_path: Path) -> None:
    history_path = tmp_path / "history.sqlite3"
    original = AntipaperService(history_path=history_path)
    original.store._related_document_finder = None
    upload = original.submit_document("quyet_dinh.pdf", SAMPLE.read_bytes(), user_id="test")
    original.shutdown()

    restarted = AntipaperService(history_path=history_path)
    assert restarted.list_history(user_id="test").total == 1
    with pytest.raises(ApiError) as error:
        restarted.get_report(upload.document_id)
    assert error.value.code == "DOCUMENT_NOT_FOUND"
    restarted.shutdown()


def test_delete_history_session_removes_only_owned_document_tasks(tmp_path: Path) -> None:
    service = AntipaperService(history_path=tmp_path / "history.sqlite3")
    first = service.history.create_task(
        user_id="owner", task_type="document_processing", display_name="first.pdf", document_id="document-1"
    )
    service.history.create_task(
        user_id="owner", task_type="question_answer", display_name="question", document_id="document-1"
    )
    service.history.create_task(
        user_id="owner", task_type="document_processing", display_name="second.pdf", document_id="document-2"
    )
    service.history.create_task(
        user_id="another-user", task_type="document_processing", display_name="other.pdf", document_id="document-1"
    )

    service.delete_history_session(user_id="owner", document_id="document-1")

    assert service.list_history(user_id="owner").total == 1
    assert service.list_history(user_id="another-user").total == 1
    with pytest.raises(ApiError) as error:
        service.get_history(user_id="owner", task_id=first.task_id)
    assert error.value.code == "HISTORY_NOT_FOUND"
    service.shutdown()


def test_delete_single_history_item_is_scoped_to_owner(tmp_path: Path) -> None:
    service = AntipaperService(history_path=tmp_path / "history.sqlite3")
    task = service.history.create_task(user_id="owner", task_type="document_processing", display_name="file.pdf")

    with pytest.raises(ApiError) as error:
        service.delete_history(user_id="another-user", task_id=task.task_id)
    assert error.value.code == "HISTORY_NOT_FOUND"
    assert service.list_history(user_id="owner").total == 1

    service.delete_history(user_id="owner", task_id=task.task_id)
    assert service.list_history(user_id="owner").total == 0
    service.shutdown()
