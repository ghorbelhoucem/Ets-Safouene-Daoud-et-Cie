#!/usr/bin/env bash
# Backup Postgres volume to a timestamped SQL dump on the host.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
OUT="backups/garage-plus-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db pg_dump -U ets ets_safouene > "$OUT"
echo "Wrote $OUT"
