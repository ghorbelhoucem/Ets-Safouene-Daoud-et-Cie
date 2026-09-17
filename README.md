# ETS Safouene Daoud et Cie — Supply Room

Full KIA-styled parts and tool management app.

## Included
- Employee PIN login and admin role
- Dashboard KPIs and low-stock alerts
- Parts: create/edit/archive, issue/consume, restock, search, minimum stock
- Tools: create/edit/archive, checkout to employees, return, current holder
- Employee management
- Full audit/activity history
- Responsive kiosk/desktop/mobile UI
- FastAPI + SQLAlchemy + PostgreSQL, with SQLite fallback
- Single Docker container for simple Railway deployment

## Environment
`DATABASE_URL` = PostgreSQL connection string
`JWT_SECRET` = long random secret
`SEED_DEMO` = `true` only for demo seed

Demo seed: Majdi / 1234 and Admin / 2026. Replace these before real company use.
