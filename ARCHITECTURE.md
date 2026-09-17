# Full Architecture Manifest

This ETS version intentionally preserves the original project's production layers:

- FastAPI backend (`backend/app`)
- PostgreSQL models/database layer
- auth + role permissions
- inventory transaction service
- API routers
- reporting/export logic
- optional Sheets sync
- optional Slack notifications
- database migration/update scripts
- backend tests
- modular frontend (`src`)
- scanner/state/domain/UI modules
- Playwright smoke tests
- CI workflow
- nginx frontend/proxy
- Docker Compose
- backup script

The source project was copied into this separate ETS project; the original source was not modified.
