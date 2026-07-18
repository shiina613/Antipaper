from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from io import BytesIO
import time
from types import SimpleNamespace

import fitz
from fastapi.testclient import TestClient

from backend.errors import ApiError
from backend.main import app, service
from backend.service import AntipaperService


client = TestClient(app)


def make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    buffer = BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def test_health_endpoint_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "antipaper-backend"


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


def test_report_terms_are_capped_and_have_single_representative_citation() -> None:
    text = ". ".join(
        [
            "nghị quyết",
            "quyết định",
            "ủy ban nhân dân",
            "hội đồng nhân dân",
            "tờ trình",
            "đề án",
            "dự thảo",
            "căn cứ pháp lý",
            "ngân sách",
            "lộ trình",
            "trách nhiệm",
            "tác động",
            "rủi ro",
            "tự luận",
            "trắc nghiệm",
            "nghị luận xã hội",
            "kinh tế học vĩ mô",
            "triết học",
            "lý luận nhà nước và pháp luật",
            "tỷ trọng đánh giá",
            "vận dụng",
        ]
    )
    response = client.post(
        "/api/v1/documents",
        files={"file": ("many-terms.pdf", f"%PDF-1.4 {text}".encode("utf-8"), "application/pdf")},
    )
    document_id = response.json()["document_id"]

    report = client.get(f"/api/v1/documents/{document_id}/report")

    assert report.status_code == 200
    terms = report.json()["terms"]
    assert 10 <= len(terms) <= 100
    assert all(len(term["citation_ids"]) <= 1 for term in terms)


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


def test_page_api_returns_source_preview_for_pdf_and_rehydrated_cache(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    pdf_bytes = make_pdf_bytes(
        "Chu tri can quyet dinh phuong an trien khai va giao trach nhiem truoc ngay 30/09/2026."
    )
    first_service = AntipaperService(artifact_root=artifact_root)
    upload = first_service.submit_document("decision-preview.pdf", pdf_bytes)
    first_page = first_service.get_page(upload.document_id, 1)

    assert first_page.source_preview is not None
    assert first_page.source_preview.data_url.startswith("data:image/png;base64,")
    assert first_page.source_preview.width > 0
    assert first_page.source_preview.height > 0

    rehydrated_service = AntipaperService(artifact_root=artifact_root)
    rehydrated_page = rehydrated_service.get_page(upload.document_id, 1)

    assert rehydrated_page.source_preview is not None
    assert rehydrated_page.source_preview.data_url.startswith("data:image/png;base64,")


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
    assert status_payload["error"]["code"] == "PROCESSING_FAILED"
    assert status_payload["error"]["message"]
    assert status_payload["error"]["retryable"] is True


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
