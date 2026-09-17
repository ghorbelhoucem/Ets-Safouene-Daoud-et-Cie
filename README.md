# ETS Safouene Daoud et Cie — Parts & Tools Management

Full production architecture derived from the original Supply Room kiosk: touchscreen frontend, FastAPI backend, PostgreSQL source of truth, audit/history, checkout/return, restocking, reports, optional Google Sheets mirror and Slack notifications.

## Stack

| Layer | Technology |
| --- | --- |
| UI | Vanilla HTML/CSS/JS (`index.html` + `src/`) |
| API | Python FastAPI (`backend/`) |
| Database | PostgreSQL |
| Integrations | Optional Google Sheets + Slack |
| Hosting | Docker / Railway |
| Tests | Pytest + Playwright |

## Architecture

- Browser UI calls `/api/*`.
- FastAPI owns authentication, inventory transactions, reports and audit data.
- PostgreSQL is the source of truth.
- Mutations use idempotency keys to make retries safe.
- Optional Google Sheets and Slack integrations remain disabled until their environment variables are configured.
- The original project remains untouched; this repository is the ETS Safouene adaptation.

## Local Docker start

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:61938`.

## Production variables

Set at least `DATABASE_URL` and a long random `JWT_SECRET`. For the included bootstrap accounts, set `ETS_ADMIN_PIN` and `ETS_STOREKEEPER_PIN` before the first database seed. Disable seeding after initial setup with `SEED_ON_STARTUP=false` if desired.

## Repository structure

```text
.
├── .github/workflows/ci.yml
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── seed.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── images/
├── scripts/
├── src/
│   ├── api/
│   ├── domain/
│   ├── scanner/
│   ├── state/
│   └── ui/
├── tests/smoke/
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── package.json
└── index.html
```

## Railway layout

Use three services in one Railway project:

- `ets-safouene-web`: root `Dockerfile`, public web frontend.
- `ets-safouene-api`: `backend/Dockerfile`, FastAPI backend.
- `Postgres`: persistent PostgreSQL database.

The root nginx config is prepared to proxy `/api` and `/health` to the private Railway API service hostname `ets-safouene-api.railway.internal:8000`.
