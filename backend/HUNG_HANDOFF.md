# Handoff Hung Backend

## Pham vi da lam

Hung phu trach backend runtime cho Antipaper: FastAPI API, upload, job status,
cache, orchestration, error handling, logging an toan, script chay backend va
dong goi deploy.

## Cac hang muc da hoan thanh

- FastAPI skeleton da co du endpoints theo `docs/API_CONTRACT.md`.
- CORS da bat de frontend co the tich hop.
- Pydantic schemas da dinh nghia cho upload, status, report, question, page va error envelope.
- Error format thong nhat theo dang `{"error": {"code", "message", "retryable"}}`.
- Upload ho tro PDF/DOCX, gioi han 25 MB.
- Upload da toi uu theo streaming request body de giam peak memory.
- Job store in-memory co polling status, stage, progress va failed state.
- Xu ly document chay qua thread pool de request upload khong bi block.
- Cache theo SHA-256 content hash da hoat dong.
- Artifact cache da luu `manifest.json`, `pages.json`, `report.json` theo document hash trong `.artifacts`.
- Cache co the rehydrate sau khi service khoi dong lai.
- Chunk cache da duoc them de report va Q&A khong rebuild chunks lap lai.
- Runtime intelligence da duoc toi uu bang cach precompute `normalized_text` va `word_count` cho moi chunk.
- PDF/DOCX parsing chay in-memory, khong can tempfile cho parsing chinh.
- Q&A tra `latency_ms` thuc te.
- Failed/timeout/invalid output tra loi ro bang error code: `PROCESSING_FAILED`, `MODEL_TIMEOUT`, `INVALID_OUTPUT`.
- Health endpoint da co tai `/health`.
- Logging chi ghi method, path, status, duration va content-length; khong log API key hoac toan van document.
- Script chay backend mot lenh: `scripts/run_backend.ps1`.
- Script package backend: `scripts/package_backend.ps1`.
- `.env.example` da co cac bien moi truong can thiet, khong chua secret that.

## Ket qua kiem thu

Da chay bang Python 3.12.13 trong `backend/.venv`:

```text
Backend contract tests: 10 passed in 1.03s
```

Da kiem tra smoke runtime:

```text
Python: 3.12.13
FastAPI: 0.139.2
PyMuPDF: 1.28.0
pytest: 9.1.1
```

Da kiem tra backend import va entrypoint:

```text
from backend.main import app -> OK
python -m backend --help -> OK
```

## Ket qua runtime

Do voi file `data/03.pdf`, kich thuoc khoang 1.27 MB:

```text
Upload:        28.75 ms
Report cold:   659.94 ms
Cache upload:  9.87 ms
Q&A:           3.97 ms
```

Ket luan: pipeline backend hien tai du nhanh cho demo local. Cache hit nhanh,
Q&A sau khi xu ly xong gan nhu tuc thi.

## Luu y quan trong

- Runtime tren hien tai la pipeline local/rule-based fallback.
- Khi tich hop goi that GPT-4o mini, bottleneck chinh se nam o LLM latency,
  batching, timeout va so lan goi model.
- Backend API/cache/upload/error handling hien da san sang de tich hop frontend.
- Khong them Redis, Celery, database hoac vector database trong scope hackathon.
- Khong commit `.env`, API key, artifact output hoac file upload tam.

## Trang thai ban giao

- HUNG-01: Done.
- HUNG-02: Done.
- HUNG-03: Done.
- HUNG-05: Done.
- Checklist trong `docs/TASKS_HUNG.md` da duoc tick hoan thanh.

## Commit da push

```text
Branch: Hung
Commit: 65cd50b HUNG backend cache and runtime hardening
Remote: origin/Hung
```
