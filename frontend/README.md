# Paperless Meetings Dashboard

Next.js dashboard frontend for the Paperless Meetings MVP, adapted from the ShadcnDeck ChatDeck shadcn template.

## Tech Stack

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- shadcn/ui-style components

## Run Locally

```powershell
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Build

```powershell
npm run build
npm run lint
```

## Current Dashboard Sections

- Upload/document status hero.
- Processing metrics from `data/01.pdf`.
- Structured summary.
- 10 terminology highlights with page references.
- 5 suggested meeting questions.
- Vietnamese Q&A answer with page citations.
- Deployment roadmap for a provincial People's Committee pilot.

## Next Integration Step

The dashboard currently uses static demo data from the Python smoke test. The next step is to add a backend API endpoint that calls `scripts/demo_meeting_ai.py` or imports the Python pipeline directly, then replace static dashboard data with live upload results.
