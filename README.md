# Telegram Anonymous Stranger Chat Bot

Telegram anonymous chat bot built with Python 3.12+, aiogram 3.x, FastAPI, PostgreSQL, Redis, SQLAlchemy 2.x, Alembic, Docker, and Nginx.

## Features

- Registration with age, gender, nickname, interests, referrals, points, and premium status
- Anonymous 1:1 matchmaking and chat relay
- Reports and moderation commands
- Telegram Stars point top-ups and VIP plan checkout
- VIP gender selection
- FastAPI health endpoints plus a protected ops stats endpoint
- Redis-backed FSM storage for bot flows

## Environment

Copy `.env.example` to `.env` and update these values:

- `BOT_TOKEN`
- `WEBHOOK_BASE_URL`
- `WEBHOOK_SECRET`
- `WEBHOOK_PATH`
- `BOT_DELIVERY_MODE`
- `POSTGRES_DSN`
- `REDIS_DSN`
- `OPS_TOKEN`
- `ADMIN_CHANNEL_ID`
- `ADMIN_USER_IDS`
- `MINIMUM_AGE`
- `SUPPORT_USERNAME`
- `LOG_LEVEL`
- `PAYMENTS_ENABLED`
- `PAYMENTS_CURRENCY`
- `POINTS_PACKAGE_10_XTR`
- `POINTS_PACKAGE_50_XTR`
- `POINTS_PACKAGE_150_XTR`
- `VIP_WEEK_XTR`
- `VIP_MONTH_XTR`
- `VIP_6MONTHS_XTR`

Current delivery modes:

- `polling` for local/dev
- `webhook` for production

## Local Setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Copy `.env.example` to `.env`.
4. Keep `BOT_DELIVERY_MODE=polling` for local work.
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

## Docker

Start the full stack:

```bash
docker compose up --build -d
```

Validate the rendered configuration:

```bash
docker compose config
```

Watch logs:

```bash
docker compose logs -f app
```

## Telegram Stars

The point top-up flow uses Telegram Stars for digital goods.

Required settings:

```env
PAYMENTS_ENABLED=true
PAYMENTS_CURRENCY=XTR
POINTS_PACKAGE_10_XTR=25
POINTS_PACKAGE_50_XTR=100
POINTS_PACKAGE_150_XTR=250
VIP_WEEK_XTR=75
VIP_MONTH_XTR=250
VIP_6MONTHS_XTR=1200
```

Notes:

- Digital goods inside Telegram should use Telegram Stars.
- Stars invoices must use `XTR`.
- No third-party provider token is required for this flow.
- VIP plan purchases extend premium access directly after payment.

Official references:

- [Telegram Bot Payments for Digital Goods and Services](https://core.telegram.org/bots/payments-stars)
- [Telegram Bot API `sendInvoice`](https://core.telegram.org/bots/api)

## HTTP Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /ops/stats`

`/ops/stats` requires `X-Ops-Token: <OPS_TOKEN>`.

## Testing

Run the test suite:

```bash
pytest
```

Useful checks:

- Open `/points` and verify the wallet shows `💳 Buy Points` and `Free`
- Complete one Telegram Stars purchase and confirm the balance increases exactly once
- Retry the same successful payment update and confirm points are not double-credited

## Admin Commands

Run these in a private chat with the bot from an admin account listed in `ADMIN_USER_IDS`:

- `/lookup <internal_user_id>`
- `/ban <internal_user_id> <reason>`
- `/unban <internal_user_id>`
