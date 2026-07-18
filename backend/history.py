"""Persistent per-user task history backed by SQLite."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from collections.abc import Iterator
from uuid import uuid4

from .errors import ApiError
from .schemas import (
    DocumentStatus,
    TaskHistoryError,
    TaskHistoryItem,
    TaskHistoryPage,
    TaskType,
)


TERMINAL_STATUSES = {"completed", "failed"}


class TaskHistoryStore:
    """Store task attempts independently from content-addressed documents.

    A fresh task row is created for every user action, including cache hits. This
    preserves the user's activity timeline without duplicating document artifacts.
    """

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
        cached: bool = False,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> TaskHistoryItem:
        now = datetime.now(timezone.utc)
        task_id = str(uuid4())
        started_at = now if status != "queued" else None
        completed_at = now if status in TERMINAL_STATUSES else None
        duration_seconds = 0.0 if completed_at is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_history (
                    task_id, user_id, task_type, document_id, display_name,
                    status, stage, progress, cached, created_at, started_at,
                    updated_at, completed_at, duration_seconds, error_code,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user_id,
                    task_type,
                    document_id,
                    display_name,
                    status,
                    stage,
                    progress,
                    int(cached),
                    self._to_iso(now),
                    self._to_iso(started_at),
                    self._to_iso(now),
                    self._to_iso(completed_at),
                    duration_seconds,
                    error_code,
                    error_message,
                ),
            )
        return self.get_task(user_id=user_id, task_id=task_id)

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
            row = connection.execute(
                "SELECT created_at, started_at, status FROM task_history WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                return
            if row["status"] in TERMINAL_STATUSES:
                return
            started_at = row["started_at"]
            if started_at is None and status != "queued":
                started_at = self._to_iso(now)
            completed_at: str | None = None
            if status in TERMINAL_STATUSES:
                completed_at = self._to_iso(now)
                if duration_seconds is None:
                    created_at = datetime.fromisoformat(row["created_at"])
                    duration_seconds = max((now - created_at).total_seconds(), 0.0)
            connection.execute(
                """
                UPDATE task_history
                SET status = ?, stage = ?, progress = ?, started_at = ?,
                    updated_at = ?, completed_at = ?, duration_seconds = ?,
                    error_code = ?, error_message = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    stage,
                    progress,
                    started_at,
                    self._to_iso(now),
                    completed_at,
                    duration_seconds,
                    error_code,
                    error_message,
                    task_id,
                ),
            )

    def attach_document(
        self,
        task_id: str,
        *,
        document_id: str,
        cached: bool,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Associate a validated upload with its pre-created history row.

        Upload rows are intentionally created before document validation so
        rejected requests are visible in history. This small transition keeps
        the database access behind the history repository instead of exposing
        its connection lifecycle to the service layer.
        """

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE task_history
                SET document_id = ?, cached = ?, error_code = ?, error_message = ?
                WHERE task_id = ?
                """,
                (
                    document_id,
                    int(cached),
                    error_code,
                    error_message,
                    task_id,
                ),
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
            task_ids = connection.execute(
                """
                SELECT task_id, cached FROM task_history
                WHERE document_id = ? AND task_type = 'document_processing'
                  AND status NOT IN ('completed', 'failed')
                """,
                (document_id,),
            ).fetchall()
        for row in task_ids:
            task_duration = duration_seconds
            # A cache hit is a distinct user action, but it does not perform
            # the original document processing again. Keep its measured task
            # duration independent from the cached document's original run.
            if status == "completed" and bool(row["cached"]):
                task_duration = 0.0
            self.update_task(
                row["task_id"],
                status=status,
                stage=stage,
                progress=progress,
                error_code=error_code,
                error_message=error_message,
                duration_seconds=task_duration,
            )

    def get_task(self, *, user_id: str, task_id: str) -> TaskHistoryItem:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_history WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
        if row is None:
            raise ApiError(
                code="HISTORY_NOT_FOUND",
                message="Task history entry not found.",
                status_code=404,
                retryable=False,
            )
        return self._row_to_item(row)

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
        if from_at is not None and to_at is not None:
            if self._as_utc(from_at) > self._as_utc(to_at):
                raise ApiError(
                    code="INVALID_TIME_RANGE",
                    message="from_at must be earlier than or equal to to_at.",
                    status_code=422,
                    retryable=False,
                )

        clauses = ["user_id = ?"]
        parameters: list[object] = [user_id]
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status)
        if task_type is not None:
            clauses.append("task_type = ?")
            parameters.append(task_type)
        if from_at is not None:
            clauses.append("created_at >= ?")
            parameters.append(self._to_iso(self._as_utc(from_at)))
        if to_at is not None:
            clauses.append("created_at <= ?")
            parameters.append(self._to_iso(self._as_utc(to_at)))

        where = " AND ".join(clauses)
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM task_history WHERE {where}",  # noqa: S608
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM task_history WHERE {where}
                ORDER BY created_at DESC, task_id DESC
                LIMIT ? OFFSET ?
                """,  # noqa: S608
                [*parameters, limit, offset],
            ).fetchall()
        return TaskHistoryPage(
            items=[self._row_to_item(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

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
                    cached INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds REAL,
                    error_code TEXT,
                    error_message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_task_history_user_created
                    ON task_history(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_history_user_status
                    ON task_history(user_id, status);
                CREATE INDEX IF NOT EXISTS idx_task_history_document_open
                    ON task_history(document_id, task_type, status);
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> TaskHistoryItem:
        error = None
        if row["error_code"] is not None:
            error = TaskHistoryError(
                code=row["error_code"],
                message=row["error_message"] or "Task failed.",
            )
        return TaskHistoryItem(
            task_id=row["task_id"],
            task_type=row["task_type"],
            document_id=row["document_id"],
            display_name=row["display_name"],
            status=row["status"],
            stage=row["stage"],
            progress=row["progress"],
            cached=bool(row["cached"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=TaskHistoryStore._parse_datetime(row["started_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=TaskHistoryStore._parse_datetime(row["completed_at"]),
            duration_seconds=row["duration_seconds"],
            error=error,
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value is not None else None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _to_iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return TaskHistoryStore._as_utc(value).isoformat(timespec="microseconds")
