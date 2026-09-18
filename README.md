# ETS Safouene Daoud et Cie — Parts & Tools Management

Production kiosk with a touchscreen frontend, FastAPI API, PostgreSQL, JWT authentication, inventory history, reports, and optional Sheets/Slack integrations.

## Structure

- Root HTML/JavaScript files: kiosk frontend
- `backend/app`: FastAPI application
- `backend/app/routers`: authentication, inventory and report routes
- `backend/app/services`: inventory, Sheets and Slack services
- `docker-compose.yml`: frontend, API and PostgreSQL
- `nginx.conf`: serves the kiosk and proxies `/api` to FastAPI

## Required production variables

Configure these on the API service before its first start:

- `DATABASE_URL`
- `JWT_SECRET` — new random value of at least 32 bytes
- `ETS_ADMIN_PIN`
- `ETS_STOREKEEPER_PIN`
- `ETS_DEVELOPER_PIN`

Never commit real PINs, passwords, webhook URLs, or service-account credentials.

## Local start

```bash
cp .env.example .env
# Replace all placeholder secrets in .env
docker compose up -d --build
```

Open http://localhost:61938.

## Railway

Use PostgreSQL plus two application services:

1. Web: repository root and root `Dockerfile`.
2. API: root directory `backend` and `backend/Dockerfile`.

Name the API service `ets-safouene-api`; nginx proxies to `ets-safouene-api.railway.internal:8000`.
