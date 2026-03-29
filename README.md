# Telegram Anonymous Stranger Chat Bot

Production-ready Telegram anonymous chat bot built with Python 3.12+, aiogram 3.x, FastAPI, PostgreSQL, Redis, SQLAlchemy 2.x, and Alembic.

## Features

- Registration with age, gender, nickname, interests, consent, referrals, points, and premium status.
- Anonymous 1:1 matchmaking with Redis-backed queueing and concurrency locks.
- Anonymous relay for text and supported Telegram media.
- `/next`, `/end`, `/report`, `/profile`, `/cancel`, `/help`.
- Telegram Stars top-ups for point packs.
- Redis-backed FSM state for multi-instance-safe user flows.
- FastAPI health endpoints plus a protected ops stats endpoint.
- Dockerized deployment with Nginx reverse proxy.

## Project Tree

```text
app/
  api/
  bot/
  db/
  schemas/
  services/
  utils/
docker/
migrations/
nginx/
tests/
.env.example
alembic.ini
docker-compose.yml
Dockerfile
pyproject.toml
README.md
```

## Environment

Copy `.env.example` to `.env` and update the values:

- `BOT_TOKEN`: Telegram bot token from BotFather.
- `WEBHOOK_BASE_URL`: Public HTTPS base URL for production webhook mode.
- `WEBHOOK_SECRET`: Shared secret used in both the webhook path and Telegram secret header.
- `WEBHOOK_PATH`: Base webhook path. Default: `/webhook/telegram`.
- `BOT_DELIVERY_MODE`: `polling` for local/dev, `webhook` for production replicas.
- `POSTGRES_DSN`: Async SQLAlchemy DSN.
- `REDIS_DSN`: Redis DSN.
- `OPS_TOKEN`: Optional token for `GET /ops/stats`.
- `ADMIN_CHANNEL_ID`: Private admin channel id for exports and reports.
- `ADMIN_USER_IDS`: Comma-separated Telegram user ids allowed to run admin commands.
- `MINIMUM_AGE`: Minimum allowed age.
- `SUPPORT_USERNAME`: Support contact shown to users.
- `LOG_LEVEL`: Logging level.
- `PAYMENTS_ENABLED`: Set to `true` to enable Telegram Stars point top-ups.
- `PAYMENTS_CURRENCY`: Must stay `XTR`.
- `POINTS_PACKAGE_10_XTR`: Telegram Stars price for the 10-point pack.
- `POINTS_PACKAGE_50_XTR`: Telegram Stars price for the 50-point pack.
- `POINTS_PACKAGE_150_XTR`: Telegram Stars price for the 150-point pack.

## Local Setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Copy `.env.example` to `.env`.
4. Keep `BOT_DELIVERY_MODE=polling` for local development.
5. Run migrations:

```bash
alembic upgrade head
```

6. Start the app:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Production Webhook Mode

1. Set `BOT_DELIVERY_MODE=webhook`.
2. Put HTTPS in front of Nginx.
3. Make sure `WEBHOOK_BASE_URL`, `WEBHOOK_PATH`, and `WEBHOOK_SECRET` are correct.
4. Start the stack. The app will register the webhook on startup.

Manual webhook registration example:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/webhook/telegram/<YOUR_WEBHOOK_SECRET>" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

## Docker Compose

1. Copy `.env.example` to `.env`.
2. For local Docker, keep `BOT_DELIVERY_MODE=polling`.
3. Start the stack:

```bash
docker compose up --build -d
```

4. Watch logs:

```bash
docker compose logs -f app
```

For scaled production replicas:

```bash
docker compose up --build -d --scale app=2
```

Use webhook mode for any multi-replica deployment. Polling mode should stay single replica.

## Admin Commands

Run these in a private chat with the bot from an admin account listed in `ADMIN_USER_IDS`:

- `/lookup <internal_user_id>`
- `/ban <internal_user_id> <reason>`
- `/unban <internal_user_id>`

## Telegram Stars Setup

1. Open BotFather and choose your bot.
2. Enable Telegram Stars payments for the bot.
3. Set `PAYMENTS_ENABLED=true`.
4. Keep `PAYMENTS_CURRENCY=XTR`.
5. Set `POINTS_PACKAGE_10_XTR`, `POINTS_PACKAGE_50_XTR`, and `POINTS_PACKAGE_150_XTR`.
6. Restart the bot.

Example:

```env
PAYMENTS_ENABLED=true
PAYMENTS_CURRENCY=XTR
POINTS_PACKAGE_10_XTR=25
POINTS_PACKAGE_50_XTR=100
POINTS_PACKAGE_150_XTR=250
```

Production notes:

- Digital goods and services inside Telegram should use Telegram Stars.
- Stars invoices must use `XTR`.
- Stars invoices use exactly one `LabeledPrice`.
- No third-party provider token is required for this Stars flow.

Official references:

- [Telegram Bot Payments for Digital Goods and Services](https://core.telegram.org/bots/payments-stars)
- [Telegram Bot API `sendInvoice`](https://core.telegram.org/bots/api)

## HTTP Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /ops/stats`

`/ops/stats` requires `X-Ops-Token: <OPS_TOKEN>` and returns:

- active searching users
- search starts
- cancels
- matches created
- average wait time
- failed handlers
- payment success count

## Testing

Run the test suite:

```bash
pytest
```

Payment checks:

- Open `/points` and verify the wallet shows `💳 Buy Points` and `Free`.
- Tap `💳 Buy Points` and confirm the 10, 50, and 150 point packs appear.
- Complete a Telegram Stars purchase and verify the user balance increases exactly once.
- Retry the same successful payment update and confirm the balance does not increase again.

## Deployment Notes

- Use HTTPS in front of Nginx. Telegram webhooks require a trusted TLS endpoint.
- Use `BOT_DELIVERY_MODE=webhook` for production.
- Run all replicas against the same PostgreSQL and Redis instances.
- Nginx is configured to resolve the `app` service through Docker DNS so webhook-mode replicas can scale cleanly.
- Keep `OPS_TOKEN` private if you enable the ops endpoint.
- Review retention policies for session exports and database logs before production rollout.

Scaling checklist:

- Set `BOT_DELIVERY_MODE=webhook`
- Set a strong `OPS_TOKEN`
- Confirm Redis persistence is enabled
- Confirm Postgres connection limits fit your replica count
- Confirm the webhook URL and secret header are valid
- Scale only the `app` service, not polling workers

## Known Limitations

- Interests are stored but not yet used for matchmaking.
- Unsupported Telegram content types are logged and politely rejected instead of being relayed.
- Transcript export is sent as a message series in the admin channel rather than a generated file attachment.
- Matchmaking currently uses one shared global matchmaking lock for simplicity and correctness. It is safe for this stage, but may need sharding later at much higher throughput.

## Next Recommended Improvements

- Add admin dashboards or protected moderation endpoints.
- Add richer anti-abuse scoring and temporary suspensions.
- Add tracing, external metrics, and alerting integrations.
- Add richer transcript packaging such as HTML or PDF exports.
