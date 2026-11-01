#!/bin/sh
# Bring the database up to date and load any new standards items, then start the app.
set -e
alembic upgrade head
python -m app.seed
exec "$@"
