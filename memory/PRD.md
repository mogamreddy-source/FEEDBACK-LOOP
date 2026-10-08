# Customer Feedback Platform POC

## Original problem statement
Build a realistic production-quality customer feedback SaaS POC proving the complete loop: owner registration, business setup, feedback template creation and customization, preview, publish, public URL and QR sharing, anonymous customer feedback submission, persistence, owner responses, and basic analytics. The provided React/FastAPI/MongoDB environment was selected over the requested Next.js/PostgreSQL stack so the app runs in the supplied workspace.

## Architecture decisions
- React 19 + React Router + Tailwind-compatible CSS for responsive owner & customer experiences.
- FastAPI REST API with MongoDB persistence (protected `MONGO_URL` / `DB_NAME`).
- JWT bearer access token with an httpOnly cookie fallback; tenant checks go through `active_workspace` + `require_role`.
- Templates store normalized question records; responses store answer records linked by question IDs; private notes embedded on response doc.
- Public pages use secure random slugs with partial-filter unique index; QR codes encode actual browser URL.
- AI sentiment via Emergent LLM key (OpenAI gpt-5.4) in FastAPI BackgroundTask; negative sentiment auto-creates an action card.
- Resend email with copy-link fallback when RESEND_API_KEY is empty.
- Weekly digest driven by Emergent platform cron at `.emergent/crons.yml` → `/api/cron/weekly-digest` (Bearer `WEBHOOK_CRON_SECRET`, enqueues to BackgroundTask, idempotent via `digest_runs`).

## User personas
- Business owner: full workspace control, invites team, manages locations, sees digest.
- Editor/Viewer: scoped actions inside the owner's workspace.
- Customer: anonymous public submission.

## Core requirements (static)
- Register → workspace → template → publish → public submit → persisted → dashboard → analytics (end-to-end).
- Public mobile-first form without customer login.
- Phase 2: team members (roles), multiple locations, AI sentiment.
- Phase 3: weekly digest email, AI action cards, per-location analytics, team private notes.

## What's been implemented
- 2026-10-08: Phase 1 MVP — auth, workspace, builder, publishing, QR, public submit, dashboard, analytics.
- 2026-10-08: Phase 2 — team invites (Resend + copy-link), locations CRUD, AI sentiment, role-based access, seed command.
- 2026-10-08: Phase 3 — weekly digest email cron, auto AI action cards on negative sentiment + manual Kanban board (/actions), per-location analytics (filter + breakdown), private team notes on each response, visual background on /templates page.
- 2026-10-08: Testing iteration 6 — 9/9 Phase 3 backend + 6/6 Phase 2 regression + 100% frontend E2E pass.

## Prioritized backlog
- P0: Phases 1–3 DONE.
- P1: Configure a real `RESEND_API_KEY` so digest + invite emails deliver (code path verified; email_sent currently False by design).
- P1: Refactor server.py & App.js into feature modules — surface area has grown past the single-file comfort zone.
- P2: Per-location drill-down drill-into responses, assignee avatars with real @-mention, drag-and-drop kanban, AI-recommended canned replies.

## Remaining next tasks
- Real `RESEND_API_KEY`.
- Response filters on `/responses` by date range + rating.
- POST /api/responses/{id}/notes should also create an audit record if the response is linked to an action card.
