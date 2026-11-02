#!/bin/sh
# Bring the database up to date and load any new standards items, then start the app.
set -e
# The database may still be starting (Aurora woken from its sleep takes several
# minutes): retry for up to 15 minutes before giving up. In a CloudFormation stack
# (DB_BOOTSTRAP_SECRET_ARN set) the app also creates its own database user first.
prepare_database() {
    if [ -n "$DB_BOOTSTRAP_SECRET_ARN" ]; then
        python -m app.app_db_user --bootstrap || return 1
    fi
    alembic upgrade head
}
tries=0
until prepare_database; do
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
