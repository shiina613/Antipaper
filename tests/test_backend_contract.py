from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


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
