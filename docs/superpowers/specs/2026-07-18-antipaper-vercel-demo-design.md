# Antipaper Vercel Demo Deployment Design

## Goal

Publish a working hackathon/demo URL on Vercel from the `deploy` branch. The demo must analyze the repository's representative PDF files, show reports and citations, and answer document-grounded questions. It is not a persistent production service.

## Decision

Use two Vercel projects from the same repository:

- `antipaper-api`: repository root, FastAPI packaged as one Python Function.
- `antipaper-web`: `frontend/` root, Next.js frontend proxying `/api/*` to `antipaper-api`.

The existing API paths and response models remain in place. On Vercel, the upload request processes its one PDF synchronously before returning instead of delegating work to a background thread. Reports, pages, and retrieval state remain in memory and under `/tmp` for the lifetime of the warm Function instance.

## Why This Shape

The current `202 Accepted` upload flow starts a thread. Vercel may freeze or terminate that work as soon as the HTTP request ends. Completing processing inside the upload request guarantees that the PDF work itself finishes while the Function is alive. Vercel still does not provide request affinity or durable local storage, so a later status, report, page, or question request can return `DOCUMENT_NOT_FOUND` after a cold start or when routed to another Function instance. This risk is explicitly accepted for the demo: the recovery path is to upload the PDF again.

The measured demo corpus fits the platform limits: the largest tested PDF is about 1.21 MiB, and the report-plus-pages JSON for the 99-page sample is about 0.86 MiB. Both are below Vercel's 4.5 MB request and response limit. The 99-page sample processes locally in about 6.4 seconds, below the Hobby Fluid Compute duration limit.

## Backend Changes

1. Make `ultralytics` optional by importing it only inside `TableDetector.load_model()`. The Vercel path keeps YOLO disabled.
2. Remove `ultralytics` from the deploy runtime so it cannot pull Torch transitively. Keep OpenCV, NumPy, and Pillow in this deployment because the current import graph requires them at startup.
3. Add an explicit Vercel FastAPI entrypoint and configuration. Exclude `frontend/`, tests, sample PDFs, models, docs, evidence, and development artifacts from the Python Function bundle.
4. Use `/tmp/antipaper` whenever a Vercel invocation needs temporary files. Do not treat it as durable storage.
5. Keep `POST /api/v1/documents` and all existing status, report, page, and question endpoints unchanged.
6. In the Vercel runtime only, make the upload handler process the document before it returns. The upload response can therefore report `completed` immediately.
7. Keep the current background executor behavior for local development.

## Frontend Changes

1. Keep the existing upload, status, report, page, and question API client functions.
2. Accept an upload response that is already `completed` and fetch its report immediately; retain polling as the local-development path.
3. When the backend returns `DOCUMENT_NOT_FOUND`, show a concise instruction to upload the PDF again.
4. Disable restoration/history behaviors that imply durable server state. Refreshing the page starts a new demo session.
5. Keep mock fallback disabled in production so backend failures are visible.

## Error Handling and Limits

- Reject unsupported file types before processing.
- Enforce a 4 MiB file ceiling for the Vercel endpoint, leaving room for multipart overhead below Vercel's 4.5 MB request limit. The legacy local API may continue allowing 25 MB.
- PDF files containing selectable text are supported. OCR-only scanned PDFs and YOLO table-image extraction are out of scope for this deployment.
- If `OPENAI_API_KEY` is absent or the provider fails, the existing grounded/rule-based fallback remains available.
- Do not expose API keys to the frontend; configure them only on `antipaper-api`.

## Verification

Before production promotion:

1. Backend import succeeds in a clean environment without Ultralytics, Paddle, or Torch.
2. Full pytest suite passes.
3. Frontend lint has no errors and production build succeeds.
4. A representative PDF completes inside the upload request and every page is available immediately afterward, including page 99 of `data/03.pdf`.
5. A question request returns an answer whose citation IDs exist in the returned report.
6. Preview deployments pass health, upload, report, citation, and Q&A smoke tests.
7. Only after preview verification, promote both projects to production and verify the public frontend URL.

## Secrets and Deployment Ownership

The local machine is already authenticated to Vercel. If present, `OPENAI_API_KEY` is copied from the local `.env` to the backend project's encrypted Vercel environment without printing it. No secret is committed. The frontend receives only the backend origin.

## Non-goals

- Durable job history, guaranteed cross-request availability, or cross-device restoration.
- Background queues, databases, Blob storage, or Redis.
- OCR/Paddle/YOLO support.
- Production SLOs, multi-tenant isolation, or long-term document retention.
