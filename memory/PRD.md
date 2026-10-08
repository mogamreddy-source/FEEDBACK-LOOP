# Customer Feedback Platform POC

## Original problem statement
Build a realistic production-quality customer feedback SaaS POC proving the complete loop: owner registration, business setup, feedback template creation and customization, preview, publish, public URL and QR sharing, anonymous customer feedback submission, persistence, owner responses, and basic analytics. The provided React/FastAPI/MongoDB environment was selected over the requested Next.js/PostgreSQL stack so the app runs in the supplied workspace.

## Architecture decisions
- React 19 + React Router + Tailwind-compatible CSS for the responsive owner and customer experiences.
- FastAPI REST API with MongoDB persistence using the protected `MONGO_URL` and `DB_NAME` values.
- JWT bearer access token with an httpOnly cookie fallback; tenant checks use the authenticated owner’s workspace ID.
- Templates store normalized question records and responses store answer records linked by question IDs.
- Public pages use secure random slugs; QR codes encode the actual browser URL.

## User personas
- Business owner: creates a workspace, builds and publishes a feedback form, then reads responses.
- Customer: opens a public link without an account, gives a rating and optional written feedback.

## Core requirements (static)
- Authenticated owner workspace, templates, questions, publishing, sharing, responses, and analytics.
- Public mobile-first form without customer login.
- No email, SMS, payments, AI, subscriptions, or enterprise features in this POC.

## What's been implemented
- 2026-10-08: Built registration/login/logout/current-user API and responsive auth experience.
- 2026-10-08: Built workspace onboarding, dashboard metrics, empty states, recent responses, templates library, presets, and business settings.
- 2026-10-08: Built template builder with question types, required flags, live preview, draft save, publish flow, random public slug, copyable URL, and real QR SVG.
- 2026-10-08: Built public feedback page with rating, yes/no, short text, long text, validation, success state, relational answer records, response list, and analytics distribution.
- 2026-10-08: Frontend production build and backend Python compilation pass.
- 2026-10-08: Analytics aligned across dashboard and analytics endpoints; added environment-backed JWT secret and login attempt lockout.

## Prioritized backlog
- P0: Validate complete register → workspace → template → publish → public response → dashboard analytics flow in browser/API tests.
- P1: Add true drag-and-drop reorder and question-level editing side panel.
- P1: Add refresh-token rotation and server-side revocation records.
- P2: Add response filters, response detail view, and workspace profile editing.

## Remaining next tasks
- Fix any blocking issues found by end-to-end testing.
- Add optional demo seed command and documented development credentials.
- Add lightweight public submission rate limiting.