#!/bin/sh
# Bring the database up to date and load any new standards items, then start the app.
set -e
# The database may still be starting (Aurora woken from its sleep takes several
# minutes): retry for up to 15 minutes before giving up.
tries=0
until alembic upgrade head; do
    tries=$((tries + 1))
    if [ "$tries" -ge 90 ]; then
        echo "Database still unreachable after 15 minutes." >&2
        exit 1
    fi
    echo "Database not ready, retrying in 10 seconds ($tries/90)..." >&2
    sleep 10
done
python -m app.seed
exec "$@"
