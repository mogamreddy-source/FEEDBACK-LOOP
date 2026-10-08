# Customer Feedback Platform POC

## Original problem statement
Build a realistic, production-quality customer feedback SaaS POC proving: owner registration → workspace → template builder with design customization and image uploads → preview → publish → public URL + QR → anonymous customer feedback → persisted → owner dashboard. React/FastAPI/MongoDB (originally requested PostgreSQL/Next.js — swap approved by user to fit the workspace).

## Architecture decisions
- React 19 SPA + FastAPI + MongoDB (Motor async). JWT bearer with httpOnly cookie fallback.
- Templates store: content (questions) + design (logo_file_id, background_file_id, colors, button_style) + category + status (DRAFT/PUBLISHED/ARCHIVED).
- Image uploads via **Emergent Object Storage** (`INTEGRATION_PROXY_URL` + `EMERGENT_LLM_KEY`). File refs in `db.files`; serving is public via UUID at `/api/files/{id}` so `<img src>` works on anonymous pages.
- Shared `BrandedFeedback` React component powers both builder preview and public `/f/{slug}` — single source of truth.
- AI sentiment on written answers via Emergent LLM (gpt-5.4) in FastAPI BackgroundTask; negative sentiment auto-creates an action card.
- Resend email with copy-link fallback (`RESEND_API_KEY` empty by design in preview).
- Weekly digest driven by Emergent platform cron `.emergent/crons.yml` → `/api/cron/weekly-digest` (Bearer `WEBHOOK_CRON_SECRET`, idempotent via `digest_runs`).

## User personas
- Business owner: full control — workspace, templates (library + builder + design), locations, team, dashboard.
- Editor/Viewer: scoped actions inside owner's workspace.
- Customer: anonymous public submission with branded form.

## Core requirements (static)
- End-to-end: register → workspace → template library → create (scratch or preset) → questions → design (logo/bg/colors/button) → preview (desktop/mobile) → publish → QR → public submit → persisted → dashboard → analytics.
- Public page must render the owner's exact logo, cover, colors, button style.
- Status model: DRAFT / PUBLISHED / ARCHIVED (archived forms cannot be reached via slug).

## What's been implemented
- 2026-10-08: Phase 1 MVP — auth, workspace, builder, publishing, QR, public submit, dashboard, analytics.
- 2026-10-08: Phase 2 — team invites (Resend + copy-link), locations CRUD, AI sentiment, seed command.
- 2026-10-08: Phase 3 — weekly digest cron, auto AI action cards + Kanban, per-location analytics, team private notes, templates background.
- 2026-10-08: Phase 4 — Template Library with status tabs + counts (All/Drafts/Published/Archived), Create picker (scratch + 5 prebuilt presets with category chips), 3-tab builder (Questions / Design / Preview), new question types (singlechoice + multichoice with option editor), real image uploads via Emergent Object Storage (logo + background), color pickers + hex sync + button style (rounded/pill/sharp), live viewport-toggled preview, duplicate/unpublish/archive/delete, public page branded with uploaded logo + cover + colors + button style, Download QR SVG.
- Testing agent iteration 7: 12/12 Phase 4 backend + 14/14 Playwright happy-path (incognito public submit verified logo + brand color `rgb(201,98,43)` applied).

## Prioritized backlog
- P0: Phases 1-4 complete.
- P1: Real `RESEND_API_KEY` to deliver weekly digest + invites.
- P1: True drag-and-drop reorder on questions and kanban cards.
- P2: Branching logic (show Q3 only if Q1 = "No"), question-level analytics drill-in.

## Remaining next tasks
- Hook up a real Resend API key.
- Per-location analytics drill-down into individual responses.
- AI-recommended canned replies on negative feedback.
