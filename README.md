# Anonymous Telegram Stranger Chat Bot

Production-ready Telegram bot foundation for anonymous 1-to-1 stranger chat. The bot acts only as a relay layer between real Telegram users, supports multiple media types, enforces registration and moderation controls, and exports ended chat transcripts plus media references to a private admin channel.

## Highlights

- Anonymous 1-to-1 relay with text, photo, video, voice, documents, and stickers
- Registration flow with age, gender, nickname, preferred gender, interests, and consent
- Queue-based matchmaking with Redis lock protection and soft preference fallback
- Centralized session end/export flow for `/end`, `/next`, reports, moderation, and failures
- PostgreSQL persistence, Redis locks/rate limits, FastAPI health/admin endpoints
- Docker, Docker Compose, Alembic migrations, Nginx reverse proxy, and structured logging

## Project Structure

```text
app/
  api/
    dependencies.py
    routes/
  bot/
    filters/
    handlers/
    keyboards/
    middlewares/
    states/
    setup.py
  db/
    models/
    repositories/
    base.py
    session.py
  schemas/
  services/
  config.py
  logging.py
  main.py
docker/
  nginx.conf
migrations/
  versions/
tests/
Dockerfile
docker-compose.yml
alembic.ini
.env.example
pyproject.toml
README.md
```

## Environment Variables

Copy `.env.example` to `.env` and set at least:

- `BOT_TOKEN`
- `WEBHOOK_BASE_URL`
- `WEBHOOK_SECRET`
- `POSTGRES_DSN`
- `REDIS_DSN`
- `ADMIN_CHANNEL_ID`
- `MINIMUM_AGE`
- `SUPPORT_USERNAME`
- `LOG_LEVEL`
- `ADMIN_USER_IDS`
- `ADMIN_API_TOKEN`

## Local Development

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2. Configure your environment

```bash
cp .env.example .env
```

Update `.env` with your Telegram bot token, webhook URL, Redis/Postgres DSNs, and admin identifiers.

### 3. Run PostgreSQL and Redis

You can use local services or Docker:

```bash
docker compose up -d postgres redis
```

### 4. Apply migrations

```bash
alembic upgrade head
```

### 5. Expose an HTTPS webhook URL

This project intentionally uses webhooks only. For local development, point `WEBHOOK_BASE_URL` to a public HTTPS tunnel such as Cloudflare Tunnel, ngrok, or your own reverse proxy.

### 6. Start the app

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker Deployment

### 1. Prepare certificates

Place your TLS certificate files in `docker/certs/`:

- `docker/certs/fullchain.pem`
- `docker/certs/privkey.pem`

### 2. Configure `.env`

Use production values and set `WEBHOOK_BASE_URL` to your public HTTPS domain.

### 3. Start the stack

```bash
docker compose up --build -d
```

Services:

- `postgres`: PostgreSQL 16
- `redis`: Redis 7 with AOF enabled
- `migrate`: one-shot Alembic migration runner
- `app`: FastAPI + aiogram webhook app
- `nginx`: TLS termination and reverse proxy

### 4. Verify health

```bash
curl https://your-domain.example/health/live
curl https://your-domain.example/health/ready
```

## FastAPI Endpoints

- `GET /health/live`
- `GET /health/ready`
- `POST /telegram/webhook`
- `GET /admin/reports`
- `GET /admin/sessions/{session_id}`
- `POST /admin/users/{user_id}/ban`
- `DELETE /admin/users/{user_id}/ban`

Admin API routes require `Authorization: Bearer <ADMIN_API_TOKEN>`.

## Moderator Workflows

- User reports create a database record, notify the admin channel, and end the active session.
- Bot admins can use `/ban`, `/unban`, `/reports`, and `/session`.
- API admins can inspect reports and apply bans through the FastAPI admin endpoints.

## Testing

Run the current service-level test suite with:

```bash
pytest
```

The initial tests cover:

- registration validation and completion
- matchmaking behavior and duplicate queue protection
- session ending and transcript export idempotency

## Deployment Notes

- The bot never forwards user identities to partners; all communication is copied through the bot.
- Transcript exports are sent to the configured private admin channel when a session ends.
- Media export uses `copy_message` where possible and posts a session reference before each copied media item.
- Rate limiting is Redis-backed and applied to commands, callbacks, and chat messages.
- The included Nginx config expects mounted TLS certificates and proxies traffic to the app container.

## Known Limitations

- The current profile matching is gender-based only; interests are stored and displayed but not yet used for ranking.
- Admin moderation routes use a bearer token and are intended for private/internal access rather than a full back-office UI.
- Transcript export retries are idempotent, but failed media copies are reported to the admin channel instead of retried through a job queue.
- FastAPI admin actions record `banned_by` and `revoked_by` as `0` because the HTTP API is system-authenticated rather than actor-identified.

## Recommended Next Improvements

1. Move transcript export and admin alerts onto a background worker queue for stronger retry guarantees.
2. Add richer matching signals such as shared interests, language, and region.
3. Replace in-memory FSM storage with Redis-backed FSM storage for multi-instance webhook workers.
4. Add a dedicated moderation dashboard with audit trails and report resolution states.
5. Add observability integrations such as Prometheus metrics and Sentry.
