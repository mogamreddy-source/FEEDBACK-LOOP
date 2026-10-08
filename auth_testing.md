# Authentication testing notes

Authentication uses JWT access tokens returned by the API and stored by the React client for this preview environment. The API also sets an httpOnly access cookie.

## Endpoints
- `POST /api/auth/register` with `full_name`, `email`, `password`
- `POST /api/auth/login` with `email`, `password`
- `GET /api/auth/me` with `Authorization: Bearer <access_token>`
- `POST /api/auth/logout`

## Expected flow
Register a unique test owner, create a workspace, then verify protected template APIs reject requests without the bearer token. Public `/api/public/feedback/{slug}` and response submission do not require authentication.