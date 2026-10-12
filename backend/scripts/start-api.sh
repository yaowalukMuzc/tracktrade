#!/bin/sh
# API container entrypoint: apply migrations, upsert reference data, serve.
set -eu

alembic upgrade head
python -m app.seeds
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
