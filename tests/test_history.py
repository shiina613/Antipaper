from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.errors import ApiError
from backend.main import app
from backend.service import AntipaperService


def test_each_upload_creates_a_distinct_persistent_task(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    service = AntipaperService(artifact_root=artifact_root)
    content = b"%PDF-1.4 persistent history"

    first = service.submit_document("meeting.pdf", content, user_id="user-1")
    service.get_report(first.document_id)
    second = service.submit_document("meeting.pdf", content, user_id="user-1")

    assert first.task_id is not None
    assert second.task_id is not None
    assert first.task_id != second.task_id
    assert second.cached is True

    restarted = AntipaperService(artifact_root=artifact_root)
    history = restarted.list_history(user_id="user-1")

    assert history.total == 2
    assert {item.task_id for item in history.items} == {first.task_id, second.task_id}
    assert all(item.status == "completed" for item in history.items)
    assert any(item.cached for item in history.items)
    cached_item = next(item for item in history.items if item.cached)
    assert cached_item.duration_seconds == 0.0


def test_history_is_isolated_by_user_and_detail_lookup(tmp_path) -> None:
    service = AntipaperService(artifact_root=tmp_path / "artifacts")
    upload = service.submit_document(
        "private.pdf",
        b"%PDF-1.4 private history",
        user_id="owner",
    )
    assert upload.task_id is not None

    assert service.list_history(user_id="other-user").total == 0
    with pytest.raises(ApiError) as error:
        service.get_history(user_id="other-user", task_id=upload.task_id)
    assert error.value.code == "HISTORY_NOT_FOUND"


def test_failed_document_records_structured_error(tmp_path) -> None:
    service = AntipaperService(artifact_root=tmp_path / "artifacts")
    upload = service.submit_document("broken.docx", b"broken", user_id="user-1")

    with pytest.raises(ApiError):
        service.get_report(upload.document_id)

    history = service.list_history(
        user_id="user-1",
        status="failed",
        task_type="document_processing",
    )
    assert history.total == 1
    assert history.items[0].error is not None
    assert history.items[0].error.code == "PROCESSING_FAILED"
    assert history.items[0].completed_at is not None


@pytest.mark.parametrize(
    ("file_name", "content", "error_code"),
    [
        ("notes.txt", b"not supported", "UNSUPPORTED_FILE"),
        ("large.pdf", b"x", "FILE_TOO_LARGE"),
    ],
)
def test_rejected_upload_is_recorded_in_history(
    tmp_path,
    monkeypatch,
    file_name: str,
    content: bytes,
    error_code: str,
) -> None:
    service = AntipaperService(artifact_root=tmp_path / "artifacts")
    if error_code == "FILE_TOO_LARGE":
        monkeypatch.setattr("backend.service.MAX_UPLOAD_BYTES", 0)

    with pytest.raises(ApiError) as error:
        service.submit_document(file_name, content, user_id="user-1")

    assert error.value.code == error_code
    history = service.list_history(user_id="user-1", status="failed")
    assert history.total == 1
    item = history.items[0]
    assert item.document_id is None
    assert item.error is not None
    assert item.error.code == error_code
    assert item.completed_at is not None


def test_history_supports_pagination_and_time_range_validation(tmp_path) -> None:
    service = AntipaperService(artifact_root=tmp_path / "artifacts")
    for index in range(3):
        service.submit_document(
            f"document-{index}.pdf",
            f"%PDF-1.4 history {index}".encode(),
            user_id="user-1",
        )

    first_page = service.list_history(user_id="user-1", limit=2, offset=0)
    second_page = service.list_history(user_id="user-1", limit=2, offset=2)
    assert first_page.total == 3
    assert len(first_page.items) == 2
    assert len(second_page.items) == 1

    now = datetime.now(timezone.utc)
    with pytest.raises(ApiError) as error:
        service.list_history(
            user_id="user-1",
            from_at=now,
            to_at=now - timedelta(minutes=1),
        )
    assert error.value.code == "INVALID_TIME_RANGE"


def test_question_answer_is_recorded_as_its_own_task(tmp_path) -> None:
    service = AntipaperService(artifact_root=tmp_path / "artifacts")
    upload = service.submit_document(
        "questions.pdf",
        b"%PDF-1.4 Antipaper meeting content",
        user_id="user-1",
    )
    service.get_report(upload.document_id)

    answer = service.answer_question(
        upload.document_id,
        "Tài liệu này nói về nội dung gì?",
        user_id="user-1",
    )
    assert answer.task_id is not None

    history = service.list_history(user_id="user-1", task_type="question_answer")
    assert history.total == 1
    assert history.items[0].task_id == answer.task_id
    assert history.items[0].status == "completed"
    assert history.items[0].stage == "ready"


def test_history_http_contract_uses_user_header() -> None:
    client = TestClient(app)
    user_id = f"history-{uuid4()}"
    upload = client.post(
        "/api/v1/documents",
        headers={"X-User-ID": user_id},
        files={"file": ("http.pdf", b"%PDF-1.4 http history", "application/pdf")},
    )
    assert upload.status_code == 202
    task_id = upload.json()["task_id"]

    listing = client.get("/api/v1/history", headers={"X-User-ID": user_id})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["task_id"] == task_id

    detail = client.get(f"/api/v1/history/{task_id}", headers={"X-User-ID": user_id})
    assert detail.status_code == 200
    assert detail.json()["document_id"] == upload.json()["document_id"]

    hidden = client.get(
        f"/api/v1/history/{task_id}",
        headers={"X-User-ID": f"other-{uuid4()}"},
    )
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "HISTORY_NOT_FOUND"
