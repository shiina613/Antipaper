# Paperless Meetings MVP Architecture

## Goal

Help provincial officials understand long PDF/Word meeting documents quickly by producing:

- Structured summaries.
- Specialized terminology explanations.
- Suggested discussion questions.
- Document-grounded Q&A with page citations.

## Processing Model

1. **Document ingestion**
   - Current MVP supports native PDFs.
   - Word support can be added through a separate loader while preserving the same downstream chunk model.

2. **Fast extraction pipeline**
   - Render PDF pages with PyMuPDF.
   - Detect table bounding boxes with YOLOv8.
   - Extract native PDF text outside table areas to avoid duplicated/noisy table text.
   - Convert detected table crops into markdown placeholders for the MVP.
   - Stitch text and markdown tables by vertical page position.

3. **Meeting intelligence layer**
   - Build page-level chunks with citations.
   - Generate structured summary sections:
     - Context.
     - Main content.
     - Decision points.
     - Impact.
     - Risks and notes.
   - Detect specialized terms and explain them.
   - Generate critical-thinking questions for officials.
   - Answer Vietnamese questions using retrieved chunks and page citations.

## Data Sources

- Public documents from provincial People's Committees.
- Government resolutions, legal normative documents, and public conference materials.
- Public 40-60 page PDF samples for stress testing.

## Deployment Roadmap

1. **MVP demo**
   - Local Python pipeline.
   - PDF upload and console/Streamlit output.
   - YOLO table detection with downloaded weights.
   - Rule-based intelligence layer for offline testing.

2. **Pilot**
   - Replace rule-based summarization and Q&A with a Vietnamese-capable LLM.
   - Add vector retrieval with page, clause, and section metadata.
   - Add Word document ingestion.
   - Add reviewer workflow for terminology validation.

3. **Production**
   - Deploy inside the People's Committee network or approved cloud.
   - Add authentication, audit logs, document retention policy, and role-based access.
   - Cache processed documents for meeting reuse.
   - Monitor latency, answer citation quality, and hallucination rate.

## Current Limitations

- Table-to-markdown is still a placeholder.
- The intelligence layer is rule-based and intended for local MVP testing.
- The current test file `data/01.pdf` has 4 pages, so it does not prove the 40+ page submission requirement yet.
