# Customer Feedback Platform POC

## Original problem statement
Build a realistic production-quality customer feedback SaaS POC proving the complete loop: owner registration, business setup, feedback template creation and customization, preview, publish, public URL and QR sharing, anonymous customer feedback submission, persistence, owner responses, and basic analytics. The provided React/FastAPI/MongoDB environment was selected over the requested Next.js/PostgreSQL stack so the app runs in the supplied workspace.

## Architecture decisions
- React 19 + React Router + Tailwind-compatible CSS for the responsive owner and customer experiences.
- FastAPI REST API with MongoDB persistence using the protected `MONGO_URL` and `DB_NAME` values.
- JWT bearer access token with an httpOnly cookie fallback; tenant checks use the authenticated owner's workspace ID.
- Templates store normalized question records and responses store answer records linked by question IDs.
- Public pages use secure random slugs; QR codes encode the actual browser URL.
- Phase 2: role-based access via `active_workspace` + `require_role`, workspace_members / locations collections, AI sentiment analysis via Emergent LLM (OpenAI gpt-5.4) as a FastAPI BackgroundTask, Resend email invites with copy-link fallback when API key is empty.

## User personas
- Business owner: creates workspace, builds and publishes forms, reads responses, invites teammates, manages multiple locations.
- Team member (editor/viewer): accepts invitation, works inside the owner's workspace with role-limited actions.
- Customer: opens a public link without an account, gives a rating and optional written feedback.

## Core requirements (static)
- Authenticated owner workspace, templates, questions, publishing, sharing, responses, and analytics.
- Public mobile-first form without customer login.
- Team members with role-based access, multiple business locations, AI sentiment analysis.

## What's been implemented
- 2026-10-08: Built MVP — auth, workspace, template builder, publishing, QR, public submit, dashboard, analytics.
- 2026-10-08: Added seed command (`python /app/backend/seed.py --fresh`) creating demo owner, ABC Restaurant workspace, 2 locations, published template with 5 questions, 8 pre-analyzed responses.
- 2026-10-08: Added team members CRUD (invite/accept/role update/remove) with Resend email + copy-link fallback and role-based route guards.
- 2026-10-08: Added multiple business locations CRUD with optional attachment on templates.
- 2026-10-08: Added AI sentiment analysis (positive/neutral/negative + summary + topics) via Emergent LLM key on public response submission, with manual re-analyze endpoint.
- 2026-10-08: Added Response Detail page, sentiment pulse on Dashboard, AI sentiment + topics on Analytics, filter pills on Responses list.
- 2026-10-08: Fixed draft template `public_slug` sparse index collision via `partialFilterExpression`.
- 2026-10-08: Testing agent iteration 5 — 8/8 backend + full frontend E2E pass.

## Prioritized backlog
- P0: Complete MVP flow + Phase 2 (team, locations, AI) — DONE.
- P1: Refactor `server.py` and `App.js` into feature-scoped files once the surface grows further.
- P1: Configure a production RESEND_API_KEY so invite emails actually deliver.
- P2: Scheduled reminders, per-location analytics breakdown, AI-recommended actions on negative feedback, workspace profile editing.

## Remaining next tasks
- Hook up a real Resend API key.
- Per-location analytics drill-down.
- Response-level reply/notes for the team.
