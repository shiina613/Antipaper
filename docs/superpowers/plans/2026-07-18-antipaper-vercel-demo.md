# Antipaper Vercel Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the existing Antipaper API contract and Next.js frontend as a working Vercel demo URL.

**Architecture:** Deploy FastAPI and Next.js as two Vercel projects. Under `VERCEL=1`, the existing upload endpoint processes one document before returning and stores its short-lived state in memory and `/tmp`; local development retains the background executor. No database, queue, storage product, or new API endpoint is introduced.

**Tech Stack:** Python 3.12, FastAPI, PyMuPDF, pytest, Next.js 16, TypeScript, Vercel Python Functions, Vercel CLI.

## Global Constraints

- Keep all existing upload, status, report, page, and question endpoint paths.
- Accept loss of documents after a cold start; the recovery action is re-upload.
- Vercel PDF upload ceiling is 4 MiB; local ceiling remains 25 MiB.
- Disable OCR, Paddle, YOLO, Ultralytics, Torch, and TorchVision in the deployed runtime.
- Never expose or commit `OPENAI_API_KEY`; configure it only on the backend Vercel project.
- Preserve the user's current `requirements.txt` and `requirements-linux.txt` changes, modifying only the dependency line required for deployment.

---

### Task 1: Make the reduced Python runtime importable

**Files:**
- Modify: `src/pipeline/table_ocr.py:14-62`
- Modify: `requirements.txt:1-15`
- Create: `tests/test_table_ocr_optional.py`

**Interfaces:**
- Consumes: existing `TableDetector.load_model() -> YOLO` behavior when YOLO is enabled.
- Produces: `pipeline.table_ocr` imports without Ultralytics; enabling YOLO without the optional package raises a clear `RuntimeError`.

- [ ] **Step 1: Add the failing optional-dependency test**

```python
import sys

import pytest

from pipeline.table_ocr import TableDetector


def test_yolo_dependency_is_loaded_only_when_detector_is_enabled(monkeypatch):
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    detector = TableDetector(model_path="missing.pt")

    with pytest.raises(RuntimeError, match="ultralytics is required only"):
        detector.load_model()
```

- [ ] **Step 2: Run the import regression and confirm failure**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_table_ocr_optional.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'ultralytics'`.

- [ ] **Step 3: Move Ultralytics behind the existing detector boundary**

```python
if TYPE_CHECKING:
    from ultralytics import YOLO

def load_model(self) -> "YOLO":
    weights = str(self.model_path) if self.model_path else "yolov8n.pt"
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "ultralytics is required only when YOLO table detection is enabled."
        ) from exc
    self.model = YOLO(weights)
    return self.model
```

Delete the `ultralytics>=8.0.0` line from `requirements.txt`; do not rewrite the user's other dependency edits.

- [ ] **Step 4: Verify the focused test**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_table_ocr_optional.py -q`

Expected: all tests in the file pass without Ultralytics installed.

- [ ] **Step 5: Commit the optional runtime fix**

```bash
git add src/pipeline/table_ocr.py requirements.txt tests/test_table_ocr_optional.py
git commit -m "fix: make table detection optional for deploy"
```

### Task 2: Make the existing upload endpoint Vercel-safe

**Files:**
- Modify: `backend/service.py:36-168`
- Modify: `backend/main.py:5-96`
- Test: `tests/test_backend_contract.py`

**Interfaces:**
- Consumes: `POST /api/v1/documents` and existing `UploadResponse`.
- Produces: `is_vercel_runtime() -> bool`; `runtime_upload_limit_bytes() -> int`; a completed or failed upload record before the Vercel response returns.

- [ ] **Step 1: Add failing Vercel runtime tests**

```python
from backend.service import runtime_upload_limit_bytes


def test_vercel_upload_processes_before_return(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    runtime = AntipaperService(artifact_root=tmp_path)
    upload = runtime.submit_document("demo.pdf", b"%PDF-1.4 demo")
    assert upload.status in {"completed", "failed"}
    assert runtime.store._documents[upload.document_id].future is None


def test_vercel_upload_limit_is_four_mib(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert runtime_upload_limit_bytes() == 4 * 1024 * 1024
```

- [ ] **Step 2: Run tests and confirm asynchronous behavior fails**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_backend_contract.py -q`

Expected: the Vercel upload test observes `queued` or a non-`None` future.

- [ ] **Step 3: Implement environment-scoped synchronous processing and limits**

```python
LOCAL_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
VERCEL_MAX_UPLOAD_BYTES = 4 * 1024 * 1024


def is_vercel_runtime() -> bool:
    return os.getenv("VERCEL") == "1"


def runtime_upload_limit_bytes() -> int:
    return VERCEL_MAX_UPLOAD_BYTES if is_vercel_runtime() else LOCAL_MAX_UPLOAD_BYTES
```

Set the default artifact root with:

```python
if artifact_root is not None:
    root = artifact_root
elif is_vercel_runtime():
    root = Path("/tmp/antipaper")
else:
    root = Path(os.getenv("ARTIFACT_DIR", ".artifacts"))
```

After storing the new record, select processing without changing the API contract:

```python
if is_vercel_runtime():
    self.process_document(record.document_id)
else:
    self._start_processing(record)
return record, False
```

Use `runtime_upload_limit_bytes()` in both the service validation and multipart reader.

- [ ] **Step 4: Verify backend contract tests**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_backend_contract.py -q`

Expected: all backend contract tests pass.

- [ ] **Step 5: Commit the Vercel runtime behavior**

```bash
git add backend/service.py backend/main.py tests/test_backend_contract.py
git commit -m "feat: process uploads inline on Vercel"
```

### Task 3: Preserve every PDF page and handle completed uploads in the frontend

**Files:**
- Modify: `backend/orchestrator.py:157-193`
- Modify: `frontend/app/page.tsx:150-210`
- Modify: `frontend/lib/antipaper-api.ts:332-349`
- Test: `tests/test_backend_contract.py`

**Interfaces:**
- Consumes: `NormalizedDocument.page_count`, `UploadResponse.status`, and existing `getDocumentReport(documentId)`.
- Produces: one `StitchedPage` for every page number from 1 through `page_count`; immediate report display when upload returns `completed`.

- [ ] **Step 1: Add a failing blank-final-page regression test**

```python
import fitz


def test_pdf_with_blank_final_page_exposes_every_page(tmp_path):
    pdf_path = tmp_path / "blank-final.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Điều 1. Nội dung có nguồn")
    document.new_page()
    document.save(pdf_path)
    document.close()

    runtime = AntipaperService(artifact_root=tmp_path / "artifacts")
    upload = runtime.submit_document(pdf_path.name, pdf_path.read_bytes())
    assert runtime.get_page(upload.document_id, 2).page_number == 2
```

- [ ] **Step 2: Run the regression test and confirm page 2 is missing**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_backend_contract.py::test_pdf_with_blank_final_page_exposes_every_page -q`

Expected: FAIL with `DOCUMENT_NOT_FOUND` for page 2.

- [ ] **Step 3: Build stitched pages from the authoritative page count**

```python
stitched_pages = [
    StitchedPage(
        page_number=page_number,
        content="\n\n".join(pages_by_number.get(page_number, [])).strip(),
    )
    for page_number in range(1, normalized.page_count + 1)
]
```

In `handleUpload`, when `upload.status === "completed"`, call `getDocumentReport(upload.document_id)`, set the report, and leave polling disabled. For other non-failed statuses, retain the existing polling path. Remove the startup effect that restores `ACTIVE_DOCUMENT_STORAGE_KEY`, because Vercel sessions are not durable.

In `fetchJson`, map an expired in-memory document to the accepted recovery action:

```typescript
if (payload.error && typeof payload.error === "object" && "code" in payload.error) {
  const apiError = payload.error as ApiErrorPayload["error"];
  message = apiError.code === "DOCUMENT_NOT_FOUND"
    ? "Phiên xử lý đã hết hạn. Vui lòng tải lại tài liệu."
    : normalizeApiError(apiError)?.message ?? message;
}
```

- [ ] **Step 4: Verify backend regression and frontend build**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_backend_contract.py::test_pdf_with_blank_final_page_exposes_every_page -q`

Expected: PASS.

Run: `cd frontend && npm run build && npm run lint`

Expected: build exits 0; lint reports 0 errors.

- [ ] **Step 5: Commit page and frontend behavior**

```bash
git add backend/orchestrator.py frontend/app/page.tsx frontend/lib/antipaper-api.ts tests/test_backend_contract.py
git commit -m "fix: complete Vercel upload flow"
```

### Task 4: Add reproducible Vercel project configuration

**Files:**
- Create: `api/index.py`
- Create: `vercel.json`
- Modify: `.gitignore`
- Modify: `backend/main.py:63-71`

**Interfaces:**
- Consumes: `backend.main.app` and the existing `/api/v1/*` routes.
- Produces: Vercel Python entrypoint `api.index:app`; health alias `GET /api/health`.

- [ ] **Step 1: Add the Python entrypoint**

```python
from backend.main import app

__all__ = ["app"]
```

- [ ] **Step 2: Add the Vercel function configuration**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 300,
      "excludeFiles": "{frontend/**,tests/**,data/**,models/**,docs/**,evidence/**,.venv/**,venv/**,.artifacts/**}"
    }
  }
}
```

Add `@app.get("/api/health")` to the existing health handler and add `/.vercel/` to the root `.gitignore`.

- [ ] **Step 3: Verify local entrypoint import and configuration syntax**

Run: `PYTHONPATH=.:src VERCEL=1 .venv/bin/python -c 'from api.index import app; print(app.title)'`

Expected: `Antipaper API`.

Run: `python -m json.tool vercel.json >/dev/null`

Expected: exit 0.

- [ ] **Step 4: Run the full local verification suite**

Run: `PYTHONPATH=.:src .venv/bin/python -m pytest -q`

Expected: all tests pass.

Run: `cd frontend && npm run build && npm run lint`

Expected: build exits 0; lint reports 0 errors.

- [ ] **Step 5: Commit deployment configuration**

```bash
git add api/index.py vercel.json .gitignore backend/main.py
git commit -m "chore: configure Vercel projects"
```

### Task 5: Preview, smoke test, and promote

**Files:**
- No committed source files.
- Generated and ignored: `.vercel/project.json`, `frontend/.vercel/project.json`.

**Interfaces:**
- Consumes: Vercel CLI authentication, local `.env`, `antipaper-api`, and `antipaper-web`.
- Produces: public production frontend and backend URLs.

- [ ] **Step 1: Link and deploy the backend preview**

```bash
npx --yes vercel@56.3.1 link --yes --project antipaper-api
npx --yes vercel@56.3.1 deploy --yes
```

Expected: a preview backend URL and successful Python Function build.

- [ ] **Step 2: Configure the backend secret without printing it**

```bash
deploy_openai_key="$(sed -n 's/^OPENAI_API_KEY=//p' .env | head -n 1)"
test -n "$deploy_openai_key"
printf '%s' "$deploy_openai_key" | npx --yes vercel@56.3.1 env add OPENAI_API_KEY preview,production --force --sensitive --yes
unset deploy_openai_key
```

Expected: Vercel confirms the sensitive variable for preview and production without printing its value.

- [ ] **Step 3: Smoke test and promote the backend**

Store the preview URL printed by the CLI in `deploy_backend_preview`, then run:

```bash
curl --fail --silent --show-error "$deploy_backend_preview/api/health"
curl --fail --silent --show-error -F 'file=@data/03.pdf;type=application/pdf' "$deploy_backend_preview/api/v1/documents" > /tmp/antipaper-upload.json
deploy_document_id="$(.venv/bin/python -c 'import json; print(json.load(open("/tmp/antipaper-upload.json"))["document_id"])')"
curl --fail --silent --show-error "$deploy_backend_preview/api/v1/documents/$deploy_document_id/status"
curl --fail --silent --show-error "$deploy_backend_preview/api/v1/documents/$deploy_document_id/report" > /tmp/antipaper-report.json
curl --fail --silent --show-error "$deploy_backend_preview/api/v1/documents/$deploy_document_id/pages/99"
curl --fail --silent --show-error -H 'Content-Type: application/json' -d '{"question":"Nội dung chính của tài liệu là gì?"}' "$deploy_backend_preview/api/v1/documents/$deploy_document_id/questions" > /tmp/antipaper-answer.json
.venv/bin/python -c 'import json; r=json.load(open("/tmp/antipaper-report.json")); a=json.load(open("/tmp/antipaper-answer.json")); assert set(a["citation_ids"]) <= set(r["citations"])'
```

Expected: all commands exit 0, page 99 exists, and every answer citation belongs to the report.

Run: `npx --yes vercel@56.3.1 deploy --prod --yes`

Expected: stable production backend URL.

- [ ] **Step 4: Link, configure, and deploy the frontend preview**

```bash
npx --yes vercel@56.3.1 link --yes --project antipaper-web --cwd frontend
```

Store the production backend URL printed by the CLI in `deploy_backend_production`, then run:

```bash
printf '%s' "$deploy_backend_production" | npx --yes vercel@56.3.1 env add BACKEND_URL preview,production --force --yes --cwd frontend
npx --yes vercel@56.3.1 deploy --yes --cwd frontend
```

Expected: Vercel confirms `BACKEND_URL` and prints a frontend preview URL.

- [ ] **Step 5: Smoke test and promote the frontend**

Store the preview URL in `deploy_frontend_preview`, then run:

```bash
curl --fail --silent --show-error "$deploy_frontend_preview" > /dev/null
npx --yes vercel@56.3.1 logs "$deploy_frontend_preview" --level error --since 10m --cwd frontend
```

Expected: homepage returns 2xx and logs contain no runtime errors. Use the browser once to upload `data/03.pdf`, open one citation, and ask one question before promotion.

Run: `npx --yes vercel@56.3.1 deploy --prod --yes --cwd frontend`

Expected: public production URL with the full demo flow.

- [ ] **Step 6: Record final evidence**

```bash
curl --fail --silent --show-error "$deploy_backend_production/api/health" > /dev/null
curl --fail --silent --show-error "$deploy_frontend_production" > /dev/null
npx --yes vercel@56.3.1 logs "$deploy_backend_production" --level error --since 10m
npx --yes vercel@56.3.1 logs "$deploy_frontend_production" --level error --since 10m --cwd frontend
```

Expected: both URLs return 2xx and recent logs contain no runtime errors. Report both URLs plus the accepted cold-start limitation to the user.
