# Paperless Meetings

MVP for helping provincial officials read, understand, and prepare for meetings from long PDF documents.

## MVP Scope

1. Extract PDF content quickly without full-document OCR.
2. Detect table regions with YOLOv8.
3. Mask table areas during native text extraction.
4. Convert detected tables to markdown placeholders.
5. Stitch page text and tables into citation-ready content.
6. Generate:
   - Structured summary.
   - Specialized terminology explanations.
   - Suggested critical-thinking questions.
   - Vietnamese document-grounded Q&A with page citations.

FastAPI and Streamlit interfaces are intentionally not implemented yet.

## Project Structure

```text
paperless_meetings/
├── data/
├── docs/
├── frontend/
├── models/
├── scripts/
├── src/
│   ├── intelligence/
│   └── pipeline/
│       ├── __init__.py
│       ├── pdf_parser.py
│       ├── processor.py
│       ├── table_ocr.py
│       └── stitcher.py
├── .env
├── requirements.txt
└── README.md
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Download YOLO Table Weights

```powershell
python download_yolo_table_weights.py
```

This stores the table detector at:

```text
models/table_detect_yolov8.pt
```

## Run Demo

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts\demo_meeting_ai.py --pdf "data\01.pdf"
```

The demo prints processing time, detected tables, structured summary, terminology highlights, suggested questions, and one grounded Q&A answer.

## Run All-In-One App

```powershell
streamlit run app.py
```

The app lets users upload a PDF, then runs extraction, table detection, structured summary, terminology explanation, suggested questions, page content preview, and a Vietnamese chatbot with citations. The chatbot only answers from the uploaded PDF; if it cannot find evidence in that document, it refuses to answer.

## Run Frontend Dashboard

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The current dashboard is adapted from the ShadcnDeck ChatDeck shadcn template and displays static demo data from `data/01.pdf`. The next step is wiring it to a backend upload/API endpoint.

## Notes

- `data/01.pdf` is a short 4-page smoke-test file.
- The challenge submission still needs a real 40+ page document test.
- Table-to-markdown and intelligence generation are MVP placeholders and should be replaced with stronger AI models for production.
