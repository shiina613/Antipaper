# Antipaper Render + Vercel Redeployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the current FastAPI backend to Render and replace the old Next.js frontend at `https://antipaper-web.vercel.app` with the current Vite frontend without changing application logic.

**Architecture:** Render runs the repository-root FastAPI process as a long-lived Python web service. The existing `antipaper-web` Vercel project builds `frontend/`, proxies `/api/v1/*` to Render, and falls back all other paths to Vite's `index.html`.

**Tech Stack:** Python 3.11+, FastAPI, Render Blueprint, Node.js 20+, React 19, Vite 7, Vercel rewrites.

## Global Constraints

- Do not modify application logic under `src/` or `frontend/src/`.
- Add only `render.yaml` and `frontend/vercel.json` as deployment configuration.
- Keep `https://antipaper-web.vercel.app` assigned to the existing Vercel project.
- Keep all API keys in Render secret settings; never commit secret values.
- Preserve the frontend's same-origin `/api/v1/*` API contract.
- Do not stage or commit the generated change in `src/antipaper.egg-info/SOURCES.txt`.

---

### Task 1: Verify the unchanged baseline

**Files:**
- Read: `pyproject.toml`
- Read: `frontend/package.json`
- Do not modify application files.

**Interfaces:**
- Consumes: existing Python and Node dependency manifests.
- Produces: a passing baseline before deployment configuration is added.

- [ ] **Step 1: Run backend tests**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests under `tests/` pass.

- [ ] **Step 2: Run frontend verification**

Run:

```bash
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: tests and lint exit successfully; Vite creates `frontend/dist/index.html`.

---

### Task 2: Add the Render backend Blueprint

**Files:**
- Create: `render.yaml`
- Do not modify: `src/**`

**Interfaces:**
- Consumes: `pyproject.toml` and the existing `python -m src` CLI.
- Produces: service `antipaper-api-shiina613` at `https://antipaper-api-shiina613.onrender.com`.

- [ ] **Step 1: Verify the configuration is absent**

Run: `test ! -e render.yaml`

Expected: exit status 0.

- [ ] **Step 2: Create `render.yaml`**

```yaml
services:
  - type: web
    name: antipaper-api-shiina613
    runtime: python
    plan: free
    buildCommand: pip install -e .
    startCommand: python -m src --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    autoDeployTrigger: commit
    envVars:
      - key: OPENAI_API_KEY
        sync: false
```

- [ ] **Step 3: Validate the Blueprint structure**

Run:

```bash
.venv/bin/python -c 'import pathlib,yaml; d=yaml.safe_load(pathlib.Path("render.yaml").read_text()); s=d["services"][0]; assert s["name"]=="antipaper-api-shiina613"; assert s["runtime"]=="python"; assert s["healthCheckPath"]=="/health"; assert s["envVars"]==[{"key":"OPENAI_API_KEY","sync":False}]'
```

Expected: exit status 0 and no output.

- [ ] **Step 4: Verify the production start command locally**

Run:

```bash
env PORT=8011 bash -c '.venv/bin/python -m src --host 127.0.0.1 --port "$PORT"' & render_pid=$!
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8011/health; then render_ready=1; break; fi
  kill -0 "$render_pid" || exit 1
  sleep 0.2
done
test "${render_ready:-0}" = 1
kill "$render_pid"
wait "$render_pid" 2>/dev/null || true
```

Expected: `/health` returns JSON containing `"service":"antipaper-backend"`.

- [ ] **Step 5: Commit only the Blueprint**

```bash
git add render.yaml
git commit -m "chore: configure Render backend"
```

Expected: the commit contains only `render.yaml`.

---

### Task 3: Add Vercel API and SPA rewrites

**Files:**
- Create: `frontend/vercel.json`
- Do not modify: `frontend/src/**`

**Interfaces:**
- Consumes: Render origin from Task 2.
- Produces: same-origin API proxying and React Router deep-link fallback.

- [ ] **Step 1: Verify the configuration is absent**

Run: `test ! -e frontend/vercel.json`

Expected: exit status 0.

- [ ] **Step 2: Create `frontend/vercel.json`**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "https://antipaper-api-shiina613.onrender.com/api/v1/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

- [ ] **Step 3: Validate JSON and rewrite order**

Run:

```bash
node -e 'const c=require("./frontend/vercel.json"); if(c.rewrites[0].source!=="/api/v1/:path*"||c.rewrites[0].destination!=="https://antipaper-api-shiina613.onrender.com/api/v1/:path*"||c.rewrites[1].destination!=="/index.html") process.exit(1)'
```

Expected: exit status 0. The API rule remains before the catch-all rule.

- [ ] **Step 4: Re-run frontend verification**

```bash
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: all three commands pass.

- [ ] **Step 5: Confirm source remains unchanged**

Run: `git diff --name-only HEAD -- src frontend/src`

Expected: no output.

- [ ] **Step 6: Commit only the Vercel configuration**

```bash
git add frontend/vercel.json
git commit -m "chore: proxy Vercel frontend to Render"
```

Expected: the commit contains only `frontend/vercel.json`.

---

### Task 4: Publish configuration to GitHub

**Files:**
- Verify: `render.yaml`
- Verify: `frontend/vercel.json`
- Do not stage: `src/antipaper.egg-info/SOURCES.txt`

**Interfaces:**
- Consumes: Tasks 2 and 3 commits.
- Produces: GitHub `main` with deployment configuration.

- [ ] **Step 1: Audit outgoing commits and local changes**

```bash
git status --short
git log --oneline origin/main..HEAD
```

Expected: the generated egg-info change remains unstaged; outgoing commits contain documentation and deployment configuration only.

- [ ] **Step 2: Push `main`**

Run: `git push origin main`

Expected: `origin/main` advances successfully.

---

### Task 5: Create and verify the Render backend

**Files:**
- Consume: `render.yaml` from GitHub `main`.
- No local file changes.

**Interfaces:**
- Consumes: GitHub and the user's OpenAI API key.
- Produces: healthy backend at `https://antipaper-api-shiina613.onrender.com`.

- [ ] **Step 1: Create the Blueprint**

In Render, select **New → Blueprint**, connect `shiina613/Antipaper`, select `main`, and apply root `render.yaml`.

Expected: one free Python web service named `antipaper-api-shiina613`.

- [ ] **Step 2: Enter the required secret**

Set `OPENAI_API_KEY` to the real key when prompted for the `sync: false` value. Do not place the value in GitHub, Vercel, screenshots, or chat.

Expected: Render stores it as a protected secret.

- [ ] **Step 3: Wait for the first deployment**

Expected build log contains `Successfully installed antipaper`; runtime log shows Uvicorn listening on Render's assigned port.

- [ ] **Step 4: Verify health**

Run: `curl -fsS https://antipaper-api-shiina613.onrender.com/health`

Expected HTTP 200 body:

```json
{"status":"ok","service":"antipaper-backend","version":"0.1.0","llm_status":"configured"}
```

If `llm_status` is `disabled`, correct `OPENAI_API_KEY` and redeploy before continuing.

---

### Task 6: Replace the old frontend in the existing Vercel project

**Files:**
- Consume: `frontend/package.json`
- Consume: `frontend/vercel.json`
- No local file changes.

**Interfaces:**
- Consumes: healthy Render backend and GitHub `main`.
- Produces: current Vite app at the unchanged Vercel domain.

- [ ] **Step 1: Open the domain-owning project**

Open the existing Vercel project whose Domains page owns `antipaper-web.vercel.app`. Do not create a replacement project.

- [ ] **Step 2: Set Git configuration**

```text
Repository: shiina613/Antipaper
Production Branch: main
Root Directory: frontend
```

Expected: the project tracks current `main`, not the old `deploy` branch.

- [ ] **Step 3: Set build configuration**

```text
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
Install Command: npm ci
```

Expected: the next deployment runs Vite, not Next.js.

- [ ] **Step 4: Deploy and promote current `main`**

Redeploy the newest `main` commit without build cache. Promote it only after a successful build.

Expected: build log contains `vite build` and not `next build`.

- [ ] **Step 5: Confirm the domain**

In **Settings → Domains**, confirm `antipaper-web.vercel.app` is assigned to Production.

Expected: the public URL remains unchanged.

---

### Task 7: Verify production end to end

**Files:**
- No local file changes.

**Interfaces:**
- Consumes: live Vercel frontend and Render backend.
- Produces: evidence that the submitted URL works end to end.

- [ ] **Step 1: Verify frontend routes**

```bash
curl -fsSI https://antipaper-web.vercel.app/
curl -fsSI https://antipaper-web.vercel.app/app
```

Expected: both return HTTP 200; HTML references `/assets/` and no longer references `/_next/`.

- [ ] **Step 2: Verify the same-origin proxy**

Run: `curl -fsS https://antipaper-web.vercel.app/api/v1/health`

Expected: Render health JSON with `"llm_status":"configured"`.

- [ ] **Step 3: Exercise the document flow**

At `https://antipaper-web.vercel.app/app`, upload `data/03.pdf`, wait for `completed`, open the report, open one citation, and ask one question.

Expected: report, citation, and answer render without a network error.

- [ ] **Step 4: Record rollback points**

Record the successful Render deploy ID and Vercel production deployment ID. Keep the prior Vercel deployment available for rollback.

Expected: Vercel rollback preserves `antipaper-web.vercel.app`.
