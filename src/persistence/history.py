"""SQLite-backed audit history for document and question tasks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4

from ..errors import ApiError
from ..schemas import DocumentStatus, TaskHistoryError, TaskHistoryItem, TaskHistoryPage, TaskType


TERMINAL_STATUSES = {"completed", "failed"}


class TaskHistoryStore:
    """Persist task metadata only; documents and reports are never persisted."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path.resolve()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = threading.Lock()
        self._initialize_schema()

    def create_task(
        self,
        *,
        user_id: str,
        task_type: TaskType,
        display_name: str,
        status: DocumentStatus = "queued",
        stage: str = "queued",
        progress: int = 0,
        document_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> TaskHistoryItem:
        now = datetime.now(timezone.utc)
        task_id = str(uuid4())
        started_at = now if status != "queued" else None
        completed_at = now if status in TERMINAL_STATUSES else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_history (
                    task_id, user_id, task_type, document_id, display_name, status,
                    stage, progress, created_at, started_at, updated_at, completed_at,
                    duration_seconds, error_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id, user_id, task_type, document_id, display_name, status,
                    stage, progress, self._to_iso(now), self._to_iso(started_at),
                    self._to_iso(now), self._to_iso(completed_at),
                    0.0 if completed_at else None, error_code, error_message,
                ),
            )
        return self.get_task(user_id=user_id, task_id=task_id)

    def attach_document(self, task_id: str, *, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE task_history SET document_id = ? WHERE task_id = ?", (document_id, task_id))

    def update_task(
        self,
        task_id: str,
        *,
        status: DocumentStatus,
        stage: str,
        progress: int,
        error_code: str | None = None,
        error_message: str | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            row = connection.execute("SELECT created_at, started_at, status FROM task_history WHERE task_id = ?", (task_id,)).fetchone()
            if row is None or row["status"] in TERMINAL_STATUSES:
                return
            started_at = row["started_at"] or self._to_iso(now)
            completed_at = self._to_iso(now) if status in TERMINAL_STATUSES else None
            if completed_at and duration_seconds is None:
                duration_seconds = max((now - datetime.fromisoformat(row["created_at"])).total_seconds(), 0.0)
            connection.execute(
                """
                UPDATE task_history
                SET status = ?, stage = ?, progress = ?, started_at = ?, updated_at = ?,
                    completed_at = ?, duration_seconds = ?, error_code = ?, error_message = ?
                WHERE task_id = ?
                """,
                (status, stage, progress, started_at, self._to_iso(now), completed_at,
                 duration_seconds, error_code, error_message, task_id),
            )

    def update_open_document_tasks(
        self,
        *,
        document_id: str,
        status: DocumentStatus,
        stage: str,
        progress: int,
        error_code: str | None = None,
        error_message: str | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT task_id FROM task_history
                   WHERE document_id = ? AND task_type = 'document_processing'
                     AND status NOT IN ('completed', 'failed')""",
                (document_id,),
            ).fetchall()
        for row in rows:
            self.update_task(row["task_id"], status=status, stage=stage, progress=progress,
                             error_code=error_code, error_message=error_message,
                             duration_seconds=duration_seconds)

    def get_task(self, *, user_id: str, task_id: str) -> TaskHistoryItem:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM task_history WHERE task_id = ? AND user_id = ?", (task_id, user_id)).fetchone()
        if row is None:
            raise ApiError(code="HISTORY_NOT_FOUND", message="Task history entry not found.", status_code=404)
        return self._row_to_item(row)

    def delete_task(self, *, user_id: str, task_id: str) -> None:
        """Delete one history entry owned by the requesting user."""
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM task_history WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            )
        if result.rowcount == 0:
            raise ApiError(code="HISTORY_NOT_FOUND", message="Task history entry not found.", status_code=404)

    def delete_session(self, *, user_id: str, document_id: str) -> None:
        """Delete all history entries associated with one document session."""
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM task_history WHERE document_id = ? AND user_id = ?",
                (document_id, user_id),
            )
        if result.rowcount == 0:
            raise ApiError(code="HISTORY_NOT_FOUND", message="History session not found.", status_code=404)

    def list_tasks(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status: DocumentStatus | None = None,
        task_type: TaskType | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
    ) -> TaskHistoryPage:
        clauses, values = ["user_id = ?"], [user_id]
        if status:
            clauses.append("status = ?")
            values.append(status)
        if task_type:
            clauses.append("task_type = ?")
            values.append(task_type)
        if from_at:
            clauses.append("created_at >= ?")
            values.append(self._to_iso(from_at))
        if to_at:
            clauses.append("created_at <= ?")
            values.append(self._to_iso(to_at))
        where = " AND ".join(clauses)
        with self._connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM task_history WHERE {where}", values).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM task_history WHERE {where} ORDER BY created_at DESC, task_id DESC LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
        return TaskHistoryPage(items=[self._row_to_item(row) for row in rows], total=total, limit=limit, offset=offset)

    def _initialize_schema(self) -> None:
        with self._schema_lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_history (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    document_id TEXT,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds REAL,
                    error_code TEXT,
                    error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_task_history_user_created ON task_history(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_history_document_open ON task_history(document_id, task_type, status);
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        try:
            connection.row_factory = sqlite3.Row
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> TaskHistoryItem:
        error = TaskHistoryError(code=row["error_code"], message=row["error_message"] or "Task failed.") if row["error_code"] else None
        return TaskHistoryItem(
            task_id=row["task_id"], task_type=row["task_type"], document_id=row["document_id"],
            display_name=row["display_name"], status=row["status"], stage=row["stage"], progress=row["progress"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            duration_seconds=row["duration_seconds"], error=error,
        )

    @staticmethod
    def _to_iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds") if value.tzinfo else value.replace(tzinfo=timezone.utc).isoformat(timespec="microseconds")
