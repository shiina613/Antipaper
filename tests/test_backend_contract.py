from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
import time
from types import SimpleNamespace

import fitz
from fastapi.testclient import TestClient

from backend.errors import ApiError
from backend.main import app, service
from backend import service as backend_service
from backend.service import AntipaperService


client = TestClient(app)


def test_health_endpoint_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "antipaper-backend"


def test_vercel_upload_processes_before_return(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VERCEL", "1")
    runtime = AntipaperService(artifact_root=tmp_path)
    calls: list[str] = []

    def process_inline(document_id: str) -> None:
        calls.append("inline")
        runtime.store._documents[document_id].status = "completed"

    def process_in_background(record) -> None:  # noqa: ANN001
        calls.append("background")

    monkeypatch.setattr(runtime.store, "process_document", process_inline)
    monkeypatch.setattr(runtime.store, "_start_processing", process_in_background)

    upload = runtime.submit_document("demo.pdf", b"%PDF-1.4 demo")

    assert upload.status == "completed"
    assert calls == ["inline"]
    runtime.shutdown()


def test_vercel_upload_limit_is_four_mib(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")

    assert backend_service.runtime_upload_limit_bytes() == 4 * 1024 * 1024


def test_vercel_default_artifacts_use_tmp(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("ARTIFACT_DIR", raising=False)

    runtime = AntipaperService()

    assert runtime.store._artifact_root == Path("/tmp/antipaper/documents").resolve()
    runtime.shutdown()


def test_invalid_file_returns_standard_error_envelope() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415
    payload = response.json()
    assert payload["error"]["code"] == "UNSUPPORTED_FILE"
    assert payload["error"]["retryable"] is False


def test_upload_status_report_page_and_question_flow() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-1.4 Antipaper sample upload", "application/pdf")},
    )
    assert response.status_code == 202
    upload = response.json()
    document_id = upload["document_id"]

    status = client.get(f"/api/v1/documents/{document_id}/status")
    assert status.status_code == 200
    assert status.json()["document_id"] == document_id

    report = client.get(f"/api/v1/documents/{document_id}/report")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["document_id"] == document_id
    assert report_payload["summary"]["context"]

    page = client.get(f"/api/v1/documents/{document_id}/pages/1")
    assert page.status_code == 200
    assert page.json()["page_number"] == 1

    answer = client.post(
        f"/api/v1/documents/{document_id}/questions",
        json={"question": "Tài liệu này nói về nội dung gì?"},
    )
    assert answer.status_code == 200
    answer_payload = answer.json()
    assert "citation_ids" in answer_payload


def test_second_upload_hits_cache() -> None:
    first = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-1.4 Antipaper sample upload", "application/pdf")},
    )
    assert first.status_code == 202
    first_payload = first.json()

    second = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-1.4 Antipaper sample upload", "application/pdf")},
    )
    assert second.status_code == 202
    second_payload = second.json()

    assert second_payload["document_id"] == first_payload["document_id"]
    assert second_payload["cached"] is True


def test_artifact_cache_survives_new_service_instance(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    first_service = AntipaperService(artifact_root=artifact_root)

    first_upload = first_service.submit_document(
        "demo.pdf",
        b"%PDF-1.4 Antipaper sample upload",
    )
    document_id = first_upload.document_id
    first_service.get_report(document_id)

    rehydrated_service = AntipaperService(artifact_root=artifact_root)
    second_upload = rehydrated_service.submit_document(
        "demo.pdf",
        b"%PDF-1.4 Antipaper sample upload",
    )

    assert second_upload.document_id == document_id
    assert second_upload.cached is True
    assert second_upload.status == "completed"

    report = rehydrated_service.get_report(document_id)
    assert report.document_id == document_id


def test_pdf_keeps_blank_final_page(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "Antipaper demo")
    document.new_page()
    file_bytes = document.tobytes()
    document.close()
    runtime = AntipaperService(artifact_root=tmp_path)

    upload = runtime.submit_document("two-pages.pdf", file_bytes)
    report = runtime.get_report(upload.document_id)
    blank_page = runtime.get_page(upload.document_id, 2)

    assert report.page_count == 2
    assert blank_page.page_number == 2
    assert blank_page.text == ""
    runtime.shutdown()


def test_too_large_file_returns_standard_error_envelope() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"x" * (25 * 1024 * 1024 + 1), "application/pdf")},
    )
    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "FILE_TOO_LARGE"
    assert payload["error"]["retryable"] is False


def test_broken_docx_marks_document_as_failed() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("broken.docx", b"not-a-real-docx-archive", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 202
    document_id = response.json()["document_id"]

    report = client.get(f"/api/v1/documents/{document_id}/report")
    assert report.status_code == 409
    assert report.json()["error"]["code"] == "PROCESSING_FAILED"

    status = client.get(f"/api/v1/documents/{document_id}/status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["status"] == "failed"
    assert status_payload["error"] is not None


def test_report_timeout_returns_model_timeout(monkeypatch) -> None:
    def slow_process(document_id):  # noqa: ANN001
        time.sleep(2.0)

    def raise_timeout(record, timeout=15.0):  # noqa: ANN001, ARG001
        raise ApiError(
            code="MODEL_TIMEOUT",
            message="Document processing timed out.",
            status_code=504,
            retryable=True,
        )

    monkeypatch.setattr(service.store, "process_document", slow_process)
    monkeypatch.setattr(service.store, "_wait_for_completion", raise_timeout)

    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo-timeout.pdf", b"%PDF-1.4 Antipaper sample upload timeout", "application/pdf")},
    )
    document_id = response.json()["document_id"]

    report = client.get(f"/api/v1/documents/{document_id}/report")
    assert report.status_code == 504
    payload = report.json()
    assert payload["error"]["code"] == "MODEL_TIMEOUT"
    assert payload["error"]["retryable"] is True


def test_question_without_evidence_returns_empty_citations() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-1.4 Antipaper sample upload", "application/pdf")},
    )
    document_id = response.json()["document_id"]

    answer = client.post(
        f"/api/v1/documents/{document_id}/questions",
        json={"question": "Ngân sách và trách nhiệm triển khai là gì?"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["insufficient_evidence"] is True
    assert payload["citation_ids"] == []


def test_invalid_orchestration_output_returns_invalid_output(monkeypatch) -> None:
    def bad_process(*, document_id, file_name, file_bytes):  # noqa: ANN001
        processed_document = SimpleNamespace(page_count=2, stitched_pages=[])
        report = SimpleNamespace(document_id=document_id, page_count=1)
        return SimpleNamespace(processed_document=processed_document, report=report)

    monkeypatch.setattr(service.store._orchestrator, "process", bad_process)

    response = client.post(
        "/api/v1/documents",
        files={"file": ("invalid-output.pdf", b"%PDF-1.4 invalid output", "application/pdf")},
    )
    document_id = response.json()["document_id"]

    report = client.get(f"/api/v1/documents/{document_id}/report")
    assert report.status_code == 502
    payload = report.json()
    assert payload["error"]["code"] == "INVALID_OUTPUT"
    assert payload["error"]["retryable"] is True
