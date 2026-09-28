#!/bin/sh
# Migrations run on every start, then the seed (idempotent), then the API.
set -e

echo "Applying database migrations"
alembic upgrade head

echo "Seeding reference data and logins"
python -m src.database.seed

if [ "${BOOTSTRAP_DEMO:-false}" = "true" ]; then
    echo "Loading the demo corpus"
    if [ "${BOOTSTRAP_PLANS:-false}" = "true" ]; then
        python -m scripts.bootstrap_demo --plans
    else
        python -m scripts.bootstrap_demo
    fi
fi

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}" --proxy-headers
