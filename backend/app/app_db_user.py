"""Give the portal its own PostgreSQL user and database, instead of Aurora's master user.

    python -m app.app_db_user --param /cloud-dev-portal/db-password

Run once, inside the running container, while the app still signs in as the
master user (the current DB_* settings): those are the credentials used to set
up. It then

1. creates the login role `portal_app` (or gives it a new password if it exists),
2. creates the database `portal`, owned by that role, which nobody else may connect to,
3. creates the tables there as `portal_app` (alembic) and copies every row from
   the current database, so nothing is lost,
4. stores the new password in SSM Parameter Store as an encrypted SecureString;
   it is never printed.

Afterwards point the app at DB_USER=portal_app, DB_NAME=portal and the
parameter (docs/aws-learner-lab.md, "Security hardening"). The master password
is then needed by nobody but you. The old copy of the tables is left untouched.
"""
import argparse
import os
import secrets
import subprocess
import sys

from sqlalchemy import Integer, create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url

from app import config
from app.db import Base
from app import models  # noqa: F401  -- registers the tables


def copy_rows(source: Engine, target: Engine) -> dict[str, int]:
    """Copy every table's rows, parents before children. Returns rows per table."""
    counts = {}
    with source.connect() as src, target.begin() as dst:
        for table in Base.metadata.sorted_tables:
            if dst.scalar(select(func.count()).select_from(table)):
                raise SystemExit(f"Table {table.name} in the new database already has rows; nothing copied.")
            # By primary key, so a parent unit comes before the units under it.
            rows = [dict(r._mapping) for r in src.execute(select(table).order_by(*table.primary_key.columns))]
            if rows:
                dst.execute(table.insert(), rows)
            counts[table.name] = len(rows)
        if target.dialect.name == "postgresql":
            # Inserting explicit ids doesn't move the id counters on: set them past
            # the copied rows. Only numbered ids have one (system ids are text).
            for table in Base.metadata.sorted_tables:
                if not isinstance(table.c.id.type, Integer):
                    continue
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"coalesce(max(id), 1), max(id) IS NOT NULL) FROM {table.name}"))
    return counts


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--param", required=True, help="SSM parameter to store the new password in")
    parser.add_argument("--user", default="portal_app")
    parser.add_argument("--database", default="portal")
    args = parser.parse_args(argv)

    admin_url = make_url(config.DATABASE_URL)
    if admin_url.get_backend_name() != "postgresql":
        raise SystemExit("This sets up a PostgreSQL user; DATABASE_URL isn't PostgreSQL.")
    if admin_url.database == args.database:
        raise SystemExit(f"The app already uses the database {args.database!r}.")

    import boto3
    from psycopg import sql

    password = secrets.token_urlsafe(32)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        role, db = sql.Identifier(args.user), sql.Identifier(args.database)
        raw = conn.connection.driver_connection
        exists = conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": args.user})
        verb = "ALTER" if exists else "CREATE"
        raw.execute(sql.SQL(verb + " ROLE {} WITH LOGIN PASSWORD {}").format(role, sql.Literal(password)))
        # PostgreSQL 16+ lets you give a database to another role only if you may
        # act as it; the master user already controls everything, so this adds nothing.
        raw.execute(sql.SQL("GRANT {} TO CURRENT_USER").format(role))
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": args.database}):
            raw.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(db, role))
        # Only its owner (and the master user) may connect to the new database.
        raw.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(db))
    print(f"Role {args.user} {'given a new password' if exists else 'created'}; database {args.database} ready.")

    app_url = admin_url.set(username=args.user, password=password, database=args.database)
    env = {**os.environ, "DATABASE_URL": app_url.render_as_string(hide_password=False)}
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=env)
    print("Tables created in the new database.")

    counts = copy_rows(create_engine(admin_url), create_engine(app_url))
    print("Copied: " + ", ".join(f"{name} {n}" for name, n in counts.items() if n))

    boto3.client("ssm", region_name=config.AWS_REGION).put_parameter(
        Name=args.param, Value=password, Type="SecureString", Overwrite=True,
        Description=f"Password of the PostgreSQL user {args.user} (app/app_db_user.py)")
    print(f"Password stored in SSM as {args.param} (SecureString).")


if __name__ == "__main__":
    main(sys.argv[1:])
