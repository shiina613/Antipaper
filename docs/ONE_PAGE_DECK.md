# Paperless Meetings - 1 Page Demo Deck

## Problem

Provincial officials often receive 40-60 page legal, administrative, and technical documents only one day before meetings. They lack time to read deeply, so meetings become longer and less prepared.

## Solution

An AI assistant that turns long meeting documents into:

- A structured summary.
- Highlighted terminology with explanations.
- Suggested questions for discussion.
- Vietnamese Q&A grounded in page-level citations.

## MVP Workflow

```text
PDF -> Page rendering -> YOLO table detection -> Native text masking
    -> Table markdown -> Page stitching -> Summary / Terms / Questions / Q&A
```

## Demo Criteria

- Upload a real document and extract content quickly.
- Return structured summary sections.
- Detect at least 10 specialized terms.
- Generate at least 5 quality discussion questions.
- Answer Vietnamese questions with page citations.

## Deployment Roadmap

1. Local demo with public documents.
2. Pilot with selected departments and validated terminology.
3. Secure deployment with access control, audit logging, and cached processed documents.

## Value

Officials can enter meetings with the core content, risks, decision points, and questions prepared before discussion starts.
