# Antipaper Render + Vercel Redeployment Design

## Goal

Replace the application currently served at `https://antipaper-web.vercel.app` with the
current Vite/FastAPI codebase while preserving that exact public URL.

## Constraints

- Do not modify application logic under `src/` or `frontend/src/`.
- Add deployment configuration only.
- Keep `https://antipaper-web.vercel.app` assigned to the existing Vercel project.
- Keep secrets out of Git and configure them in the hosting dashboards.
- Preserve the current API contract at the same-origin `/api/v1/*` paths.

## Architecture

The existing Vercel project `antipaper-web` serves the Vite production build from the
repository's `frontend/` directory. A Vercel rewrite forwards `/api/v1/*` to a Render web
service at `https://antipaper-api-shiina613.onrender.com`. A second rewrite sends all
non-API routes to `index.html` so React Router routes work when opened directly.

The Render service runs the current FastAPI application from the repository root. Render
installs the Python package from `pyproject.toml`, starts `python -m src` on the platform's
assigned `$PORT`, and checks `/health` for readiness.

```text
Browser
  -> https://antipaper-web.vercel.app
       -> Vite static frontend
       -> /api/v1/* rewrite
            -> https://antipaper-api-shiina613.onrender.com/api/v1/*
                 -> FastAPI
                 -> OpenAI API
```

## Deployment Configuration

Only two deployment files are required:

- `render.yaml` defines the Render Python web service, build/start commands, health check,
  and secret environment variable names.
- `frontend/vercel.json` defines the external API rewrite and the Vite SPA fallback.

The Vercel project settings are:

- Git repository: `shiina613/Antipaper`
- Production branch: `main`
- Root directory: `frontend`
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

The Render service settings are:

- Service name: `antipaper-api-shiina613`
- Runtime: Python
- Build command: `pip install -e .`
- Start command: `python -m src --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Required secret: `OPENAI_API_KEY` or `LLM_API_KEY`
- Optional secret: `TAVILY_API_KEY`
- Non-secret defaults remain those already defined by the application.

## Request and Data Flow

1. The browser loads the Vite bundle from the unchanged Vercel domain.
2. The frontend sends relative requests such as `POST /api/v1/documents`.
3. Vercel proxies the request to the Render service without exposing a different API URL
   to the browser.
4. FastAPI accepts the upload and processes it in the Render process.
5. Frontend polling, report retrieval, page preview, history, and questions follow the same
   rewrite and retain the existing API contract.

## Runtime Limitations

The current backend intentionally stores uploaded document content, reports, page previews,
and retrieval indexes in process memory. Render restarts or redeployments therefore remove
active document sessions. SQLite history also remains ephemeral unless a persistent disk is
added. This is acceptable for the submitted demo and does not require application changes.

On a free Render service, the backend may sleep while idle, so the first request can take
longer. The frontend must be tested after the health endpoint has awakened successfully.

## Error Handling and Security

- Render must not be considered ready until `/health` returns HTTP 200 with
  `"service":"antipaper-backend"`.
- Vercel deployment is not promoted if the frontend build fails.
- API secrets exist only in Render environment settings and are never placed in
  `render.yaml`, `vercel.json`, or Vercel frontend variables.
- `TAVILY_API_KEY` remains optional; missing Tavily configuration only disables related
  document enrichment.
- Rollback uses Vercel's previous production deployment without changing the public domain.

## Verification

Before production promotion:

1. Run backend tests with `.venv/bin/python -m pytest -q`.
2. Run frontend tests, lint, and build from `frontend/`.
3. Confirm Render `/health` returns HTTP 200 and `llm_status` is not `disabled`.
4. Confirm the Vercel root and `/app` both return the new Vite application.
5. Confirm `https://antipaper-web.vercel.app/api/v1/health` reaches Render.
6. Upload one text-based sample PDF, wait for completion, open its report and one citation,
   then ask one question.
7. Confirm the production domain remains exactly `https://antipaper-web.vercel.app`.

## Deployment Order

1. Add and push the two deployment configuration files.
2. Create the Render service from `render.yaml` and configure its secrets.
3. Verify the Render health endpoint.
4. Update the existing `antipaper-web` Vercel project to build `main` from `frontend/`.
5. Redeploy and promote the successful Vercel build to Production.
6. Run the end-to-end verification checklist on the unchanged public URL.
