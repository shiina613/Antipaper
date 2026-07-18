# Antipaper

Trá»£ lÃ½ AI giÃºp cÃ¡n bá»™ Ä‘á»c nhanh tÃ i liá»‡u há»p dÃ i, chuáº©n bá»‹ cÃ¢u há»i vÃ  tra cá»©u báº±ng tiáº¿ng Viá»‡t vá»›i citation Ä‘áº¿n trang/má»¥c/Ä‘iá»u.
<img width="1939" height="4097" alt="mermaid-diagram-2026-07-18-075329" src="https://github.com/user-attachments/assets/e50b2b98-9fe2-4cdd-8f85-1cd4eb7334f4" />

## Tráº¡ng thÃ¡i hiá»‡n táº¡i

Kho mÃ£ nguá»“n Ä‘ang á»Ÿ má»©c khung ká»¹ thuáº­t:

- Da co luong PDF bang PyMuPDF, FastAPI backend va giao dien Next.js tich hop.
- ÄÃ£ cÃ³ FastAPI job/cache, canonical document contract, grounded Q&A vÃ  citation cáº¥p trang/má»¥c/Ä‘iá»u.
- Report dÃ¹ng LLM map-reduce khi cáº¥u hÃ¬nh model; heuristic chá»‰ lÃ  fallback cÃ³ gáº¯n nhÃ£n vÃ  khÃ´ng Ä‘Æ°á»£c qua release gate.
- ÄÃ£ cÃ³ benchmark deterministic vÃ  DeepEval; semantic embedding vÃ  DOCX production váº«n lÃ  háº¡ng má»¥c tiáº¿p theo.
- Kho `data/` Ä‘Ã£ cÃ³ nhiá»u PDF tá»« 40 trang; tÃ i liá»‡u demo Ä‘Æ°á»£c chá»n qua `DEMO_DOCUMENT_PATH`, khÃ´ng phá»¥ thuá»™c tÃªn file.

Xem tráº¡ng thÃ¡i chi tiáº¿t táº¡i [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md).

## TÃ i liá»‡u lÃ m viá»‡c

| TÃ i liá»‡u | Má»¥c Ä‘Ã­ch |
|---|---|
| [problem.txt](problem.txt) | Äá» bÃ i vÃ  pháº¡m vi sáº£n pháº©m |
| [docs/PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | NgÆ°á»i dÃ¹ng, yÃªu cáº§u vÃ  pháº¡m vi MVP |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Kiáº¿n trÃºc xá»­ lÃ½ vÃ  quyáº¿t Ä‘á»‹nh ká»¹ thuáº­t |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | NgÄƒn xáº¿p cÃ´ng nghá»‡ dÃ¹ng trong 48 giá» |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md) | Há»£p Ä‘á»“ng tÃ­ch há»£p backendâ€“frontend |
| [docs/BUILD_PLAN_48H.md](docs/BUILD_PLAN_48H.md) | Timeline, má»‘c khÃ³a vÃ  phÆ°Æ¡ng Ã¡n dá»± phÃ²ng |
| [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) | CÃ¡ch kiá»ƒm chá»©ng tiÃªu chÃ­ ná»™p bÃ i |
| [docs/AI_COLLABORATION_LOG.md](docs/AI_COLLABORATION_LOG.md) | Nháº­t kÃ½ vÃ  báº±ng chá»©ng cá»™ng tÃ¡c vá»›i cÃ¡c cÃ´ng cá»¥ AI |
| [docs/ONE_PAGE_DECK.md](docs/ONE_PAGE_DECK.md) | Ná»™i dung deck má»™t trang |
| `docs/TASKS_*.md` | Viá»‡c cá»¥ thá»ƒ cá»§a tá»«ng thÃ nh viÃªn |

## PhÃ¢n cÃ´ng 5 ngÆ°á»i

| ThÃ nh viÃªn | Máº£ng phá»¥ trÃ¡ch | Chi tiáº¿t |
|---|---|---|
| Háº­u | TÃ³m táº¯t, thuáº­t ngá»¯, cÃ¢u há»i AI vÃ  OCR fallback | [TASKS_HAU.md](docs/TASKS_HAU.md) |
| Tuáº¥n | Nháº­p PDF/DOCX, parse cáº¥u trÃºc, citation vÃ  LLM client | [TASKS_TUAN.md](docs/TASKS_TUAN.md) |
| TÃ¹ng | Giao diá»‡n, tÃ­ch há»£p, benchmark nghiá»‡m thu, demo vÃ  deck | [TASKS_TUNG.md](docs/TASKS_TUNG.md) |
| TÃ¹ng Anh | Truy há»“i, Q&A, vÄƒn báº£n liÃªn quan, kiá»ƒm tra citation | [TASKS_TUNG_ANH.md](docs/TASKS_TUNG_ANH.md) |
| HÆ°ng | FastAPI, job/cache, xá»­ lÃ½ bottleneck runtime vÃ  Ä‘Ã³ng gÃ³i backend | [TASKS_HUNG.md](docs/TASKS_HUNG.md) |

## Cáº¥u trÃºc chÃ­nh

```text
Antipaper/
├── backend/              # FastAPI, orchestration, pipeline, intelligence, retrieval
├── data/                 # PDF mau cong khai
├── docs/                 # Kien truc, ke hoach, kiem thu va task
├── evals/                # Release dataset, adapters va DeepEval suite
├── evidence/             # Ket qua benchmark co truy vet
├── frontend/             # Next.js dashboard
└── scripts/              # Script demo/benchmark
```

## Cháº¡y tÃ­ch há»£p backend vÃ  frontend

YÃªu cáº§u Python 3.12 vÃ  Node.js 20+. Cá»­a sá»• PowerShell thá»© nháº¥t:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
.\scripts\run_backend.ps1 -Reload
```

Backend Ä‘á»c `.env` khi khá»Ÿi Ä‘á»™ng vÃ  phá»¥c vá»¥ táº¡i `http://127.0.0.1:8000`. KhÃ´ng cÃ³
`LLM_API_KEY`, pipeline váº«n cháº¡y báº±ng `heuristic_fallback` vÃ  frontend sáº½ cáº£nh bÃ¡o
rÃµ Ä‘Ã¢y lÃ  káº¿t quáº£ dá»± phÃ²ng.

Kiem tra backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Cá»­a sá»• PowerShell thá»© hai:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Má»Ÿ `http://localhost:3000`. Next.js chuyá»ƒn tiáº¿p `/api/v1/*` sang backend, vÃ¬ váº­y
trÃ¬nh duyá»‡t khÃ´ng cáº§n cáº¥u hÃ¬nh URL API hoáº·c xá»­ lÃ½ CORS. Äá»ƒ dÃ¹ng backend khÃ¡c:

```powershell
$env:ANTIPAPER_BACKEND_URL="http://127.0.0.1:9000"
npm run dev
```

`requirements.txt` á»Ÿ thÆ° má»¥c gá»‘c lÃ  mÃ´i trÆ°á»ng Ä‘áº§y Ä‘á»§ cho GPU NVIDIA, OCR vÃ 
DeepEval; khÃ´ng cáº§n cÃ i gÃ³i náº·ng nÃ y chá»‰ Ä‘á»ƒ cháº¡y vertical slice web. LuÃ´n gá»i pip
qua `python -m pip` sau khi kÃ­ch hoáº¡t `.venv` Ä‘á»ƒ trÃ¡nh cÃ i nháº§m vÃ o Python há»‡ thá»‘ng.

## GÃ³i deploy backend

```powershell
.\scripts\package_backend.ps1
```

Bundle Ä‘áº§u ra máº·c Ä‘á»‹nh náº±m á»Ÿ `.artifacts\antipaper-backend.zip`.

## Cháº¡y evaluation benchmark

PR gate khÃ´ng gá»i LLM judge vÃ  cÃ³ thá»ƒ cháº¡y offline:

```powershell
python -m pytest
python -m evals.run --suite smoke --output evidence/benchmark-smoke.json
```

Release gate dÃ¹ng pipeline tháº­t vÃ  DeepEval 4.1.0. Cáº§n cáº¥u hÃ¬nh
`DEMO_DOCUMENT_PATH`, `LLM_API_KEY`, `LLM_MODEL`, `OPENAI_API_KEY` vÃ 
`EVAL_JUDGE_MODEL`; judge máº·c Ä‘á»‹nh lÃ  `gpt-5.4`, temperature 0.

```powershell
python -m pip install -r requirements.txt
python -m evals.run --suite full --output evidence/benchmark.json
$env:PYTHONIOENCODING="utf-8" # cáº§n cho Rich/DeepEval trÃªn Windows
deepeval test run evals/tests
```

Dataset release á»Ÿ `evals/datasets/demo_v1.jsonl`. Bá»™ deterministic tÃ¡i sá»­ dá»¥ng
`backend/retrieval/golden.py`; khÃ´ng cÃ³ evaluator golden thá»© hai. Cháº¿ Ä‘á»™
`heuristic_fallback` chá»‰ giá»¯ kháº£ dá»¥ng runtime vÃ  khÃ´ng Ä‘Æ°á»£c phÃ©p qua release
gate. Thá»i gian judge khÃ´ng Ä‘Æ°á»£c tÃ­nh vÃ o latency cá»§a pipeline.

## Logging an toÃ n

- Backend chá»‰ log method, path, status, duration vÃ  content-length.
- KhÃ´ng log toÃ n vÄƒn tÃ i liá»‡u upload.
- KhÃ´ng log API key, token hoáº·c giÃ¡ trá»‹ secret-like trong message.

## Quy táº¯c lÃ m viá»‡c 48 giá»

- Chá»‘t schema vÃ  API trÆ°á»›c khi chia nhÃ¡nh.
- Má»—i nhiá»‡m vá»¥ cÃ³ Ä‘iá»u kiá»‡n hoÃ n thÃ nh vÃ  báº±ng chá»©ng cháº¡y Ä‘Æ°á»£c.
- Merge theo lÃ¡t cáº¯t end-to-end; khÃ´ng chá» Ä‘áº¿n cuá»‘i má»›i tÃ­ch há»£p.
- Sau giá» 32 chá»‰ sá»­a lá»—i P0/P1 vÃ  hoÃ n thiá»‡n demo.
