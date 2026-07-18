# Antipaper Figma Frontend Design

## Goal

Build the frontend as the full Antipaper app shell shown in the Figma file, not the current marketing-style dashboard. The app should use the real API contract in `docs/API_CONTRACT.md` as the primary data path and fall back to mock data when the backend is unavailable, so the UI remains demoable.

Figma source:

- File: `387dGwclSTbq11iZdGW0Fd`
- Page node: `0:1`
- Key screens: Upload, Processing, Glossary, Q&A with citation viewer

## Scope

In scope:

- Replace route `/` with the Antipaper app shell.
- Implement the left side navigation, center workspace, and right citation viewer from the Figma design.
- Support Upload, Processing, Glossary/Summary, Q&A, and Citation views.
- Use API endpoints from `docs/API_CONTRACT.md` first.
- Fall back to contract-shaped mock data on network/backend failure.
- Validate PDF/DOCX upload files up to 25 MB.
- Render status, progress, elapsed time, report, glossary, suggested questions, Q&A answers, and citations.
- Handle empty, uploading, queued, processing, completed, failed, insufficient-evidence, and citation-loading states.
- Keep the interface responsive for mobile, tablet, and desktop.
- Verify with `npm run lint` and `npm run build` in `frontend/`.

Out of scope for this pass:

- Authentication, SSO, permissions, audit log, production storage, and a full PDF canvas viewer.
- Adding new frontend dependencies unless an existing dependency cannot cover a required control.
- Building the old marketing sections from `frontend/components/Blocks`.

## Product Behavior

The default user journey is:

1. Open `/`.
2. See the Antipaper shell with an empty or demo-ready state.
3. Upload a PDF/DOCX document.
4. Watch pipeline status while the backend processes it.
5. Review the completed report: summary, glossary, suggested questions, and related evidence.
6. Ask Vietnamese questions in the Q&A composer.
7. Click citations to open the right-side citation viewer.

When the backend is not reachable, the same flow should continue with mock data and a subtle "demo fallback" indicator. The UI must not present fallback data as a live backend result.

## Architecture

### Page Shell

`frontend/app/page.tsx` becomes the main client app shell. It owns top-level UI state and passes data to small local components. The current global marketing navbar/footer should no longer appear around this app screen; the app shell provides its own navigation.

Recommended component boundaries:

- `AntipaperShell`: page-level state and layout.
- `SideNav`: product navigation and new-document action.
- `UploadWorkspace`: file picker/dropzone and upload validation.
- `ProcessingWorkspace`: circular/progress status and processing log.
- `ReportWorkspace`: summary, terms, suggested questions, and related context.
- `QaWorkspace`: chat transcript and question composer.
- `CitationViewer`: selected citation/page/excerpt panel.

Keep these components in as few files as is still readable. Start with one page file plus one API/mock helper if practical.

### API Adapter

Create a small frontend adapter for:

- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}/status`
- `GET /api/v1/documents/{document_id}/report`
- `POST /api/v1/documents/{document_id}/questions`
- `GET /api/v1/documents/{document_id}/pages/{page_number}`

The adapter should:

- Use relative `/api/v1` URLs by default.
- Convert standard API errors into a UI-friendly shape.
- Fall back to mock data on fetch/network/backend failure.
- Mark fallback responses so the UI can show demo status.
- Preserve UTF-8 Vietnamese text.

Polling should be simple: after upload, poll status until `completed` or `failed`; when completed, fetch the report. Do not add a state-machine library.

### Mock Data

Mock data should match `docs/API_CONTRACT.md`:

- `document_id`
- status response fields
- report fields
- citations map
- Q&A response shape
- page/excerpt response shape

The mock scenario should use Vietnamese meeting-document content where possible, while retaining the Figma examples where they help match the design.

## Visual Design

Match the Figma "Quiet Executive" direction:

- Three-column desktop layout: 280px side nav, flexible center workspace, 320-380px citation panel.
- Off-white surfaces, subtle borders, low shadows, restrained green accent.
- Rounded corners around 8px for cards/buttons.
- Dense, readable operational UI, not a landing page.
- Use existing Tailwind v4 and current UI primitives.
- Use `lucide-react` icons instead of downloaded Figma icon assets.
- Use existing fonts from the app; approximate Be Vietnam Pro/Space Mono with available sans/mono tokens unless adding fonts is explicitly needed.

Responsive behavior:

- Desktop: fixed full-height shell with side nav and citation panel visible.
- Tablet: side nav can narrow or stack; citation viewer may collapse below content.
- Mobile: side nav becomes top/compact navigation, center workspace is primary, citation viewer opens as an inline panel or drawer-like section.

## States

Empty:

- Show upload workspace as the primary action.
- Q&A is disabled until a completed report exists.

Uploading:

- Disable upload controls.
- Show selected file name and upload status.

Queued/Processing:

- Show current stage, progress, elapsed seconds, and pipeline steps.
- Processing log should update from known stages or mock progression.

Completed:

- Render report sections and enable Q&A.
- Render citation badges only for citation IDs that exist in the report citations map.

Failed:

- Show friendly error message, error code when available, and retry when `retryable=true`.

Insufficient evidence:

- Render the AI refusal answer.
- Do not render empty citation badges as if they were evidence.

Citation loading:

- Show citation panel loading state while fetching page/excerpt.
- If page API fails, use the excerpt from the report citation as fallback.

## Data Flow

Upload flow:

1. User selects PDF/DOCX.
2. UI validates file type and 25 MB limit.
3. Adapter posts `FormData` to `/api/v1/documents`.
4. UI stores `document_id`, fallback flag, and status.
5. UI polls status.
6. Completed status triggers report fetch.

Q&A flow:

1. User submits a Vietnamese question.
2. UI appends user message optimistically.
3. Adapter posts to `/questions`.
4. UI appends AI message with citations or insufficient-evidence state.

Citation flow:

1. User clicks a citation badge.
2. UI selects citation metadata from report.
3. Adapter fetches `/pages/{page_number}`.
4. Citation viewer renders page label, file name, location metadata, excerpt, and highlight.

## Error Handling

File validation errors should be client-side and immediate:

- Unsupported type: "Chỉ hỗ trợ PDF hoặc DOCX."
- Too large: "Tệp vượt quá giới hạn 25 MB."

API errors should use `error.code`, `error.message`, and `retryable` from the contract when present. Unknown errors should show a short generic message and allow returning to upload/demo state.

Fallback mode should be visible but quiet, for example a small "Demo fallback" badge in the header or processing panel.

## Accessibility

- Keep `lang="vi"` in the root layout.
- Icon-only buttons need `aria-label`.
- Inputs need labels or accessible placeholder/context.
- Buttons and badges must avoid clipped Vietnamese text.
- Keyboard users must be able to upload, submit a question, and activate citations.
- Preserve contrast in light and dark tokens where dark mode remains available.

## Acceptance Criteria

- `npm run lint` passes in `frontend/`.
- `npm run build` passes in `frontend/`.
- `/` shows the Antipaper app shell, not the old hero landing page.
- The UI can upload a valid PDF/DOCX and follow API status to report.
- When API calls fail because the backend is unavailable, the UI falls back to mock data and visibly marks fallback mode.
- Processing state shows stage, progress, elapsed time, and pipeline steps.
- Completed report renders summary, terms/glossary, suggested questions, and citation badges.
- Q&A sends questions to the API when possible and falls back to mock answers when necessary.
- Insufficient-evidence answers show no fake citations.
- Citation clicks update the citation viewer with page/excerpt data or report-excerpt fallback.
- Layout remains usable on mobile and desktop.

## Implementation Notes

- Prefer native file input and fetch APIs.
- Prefer existing Tailwind, shadcn-style UI components, and `lucide-react`.
- Do not add routing unless a screen genuinely needs its own URL; tabs/views inside the app shell are enough for this pass.
- Keep mock fixtures close to the adapter so the fallback behavior is easy to remove or tighten later.
- Avoid reusing marketing blocks that do not match the Figma app shell.
