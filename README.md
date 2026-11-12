# Cloud Internal Developer Portal

Lists every Cloud system, who owns it and where it stands in development, so leaders and peers can understand and review any project without a meeting.

**Owner:** <name> · **Backup person:** <name> · **Production URL:** not live yet

## Run it on your computer

You need:

- Python 3.11 or newer
- Node.js 24
- Access to the Cloud GitLab group

```bash
git clone <repository-url>
cd developer-portal
cp .env.example backend/.env

cd frontend
npm ci
npm run build
cd ../backend
pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m app.seed --demo
python -m uvicorn app.main:app --port 8000
```

Before starting, set `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` in `backend/.env` (see `.env.example`): that account is created as an admin at start-up. Open <http://localhost:8000> and sign in with it. Without SMTP settings, emails (sign-up verification, password reset) are written to the server log, links included. `--demo` adds four sample systems, all owned by the seed admin (run again, it hands any demo systems back to them); leave it out for an empty portal. On Windows, `start.bat` does all of this and opens the browser; `start.bat build` rebuilds the frontend first.

To work on the frontend with live reload, run `npm run dev` in `frontend/` with `NEXT_PUBLIC_API_BASE=http://localhost:8000`, and set `ALLOWED_ORIGINS=http://localhost:3000` in `backend/.env`.

## Run the tests

```bash
python -m pytest infra   # the AWS sleep/wake function
cd backend
python -m pytest
python -m alembic check
cd ../frontend
npx eslint src
npx tsc --noEmit
```

## Change the database

Edit `backend/app/models.py`, then create a migration and commit it with the change:

```bash
cd backend
python -m alembic revision --autogenerate -m "short description"
```

The container applies new migrations when it starts.

## Secrets and leak scanning

Each system has a secrets vault and leak alerts in its **รหัสลับและความปลอดภัย** tab, and the **ความปลอดภัย** page lists alerts across systems (decision [0009](docs/decisions/0009-secrets.md)).

```bash
cd backend
python -m app.leak_scan     # scan every system now, as the schedule does (for a cron job)
python -m app.vault rotate  # after putting a new key first in SECRETS_ENCRYPTION_KEY
```

To keep a documented example value from being reported, put `portal:ignore-secret` on the same line.

## Deploy

The app deploys through the standard pipeline (`.gitlab-ci.yml`). Every push runs the tests. Merging into `main` builds the image. Deploying to production is a manual step in the pipeline. No manual steps on the server.

Before the first deploy, the deployer fills in the `<...>` values in `deployment.template.yaml` and creates the Kubernetes secret, as described at the top of that file.

## Settings

All settings are listed in `.env.example`.

| Variable | What it is for | Example |
| --- | --- | --- |
| `ENVIRONMENT` | `production` turns on safe defaults and requires the email settings | `production` |
| `JWT_SECRET_KEY` | Signs session cookies; required in production | in the Kubernetes secret |
| `SECRETS_ENCRYPTION_KEY` | Encrypts each system's secrets vault; required in production. Back it up: without it the vault can't be read. Comma-separated to rotate | in the Kubernetes secret |
| `SECRET_SCAN_INTERVAL_HOURS` | How often every system is scanned for leaked secrets; `0` turns the in-app schedule off | `24` |
| `DATABASE_URL` | Database address; SQLite by default | `sqlite:////app/instance/portal.db` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Aurora PostgreSQL in parts, used when `DATABASE_URL` is empty | `portal.cluster-….us-east-1.rds.amazonaws.com` |
| `DOCS_BUCKET`, `DOCS_PREFIX`, `AWS_REGION` | S3 bucket for the guide's markdown files; empty keeps them in the database | `cloud-dev-portal-docs` |
| `ALLOWED_HOSTS` | Hostnames the app answers to | `devportal.cloud.internal` |
| `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD` | The first admin, created at start-up | `it.lead@example.org` |
| `SUPPORT_EMAIL` | Contact on the sign-in page, by email and Webex; defaults to the seed admin | `it.lead@example.org` |
| `SMTP_*`, `MAIL_FROM` | Email for sign-up verification and password reset (Resend works); unused with Cognito | see `.env.example` |
| `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_DOMAIN` | Sign-in through a Cognito user pool, when all three are set; empty keeps the portal's own passwords | `us-east-1_AbC123` |
| `PUBLIC_BASE_URL` | The portal's address, for links in emails and Cognito's return address | `https://devportal.cloud.internal` |
| `ALLOWED_EMAIL_DOMAINS` | Only these domains may sign up; empty allows any | `nstda.or.th` |
| `KB_BASE_URL` | Knowledge base address for checklist links | `https://kb.cloud.internal` |

## More documentation

- [Premises](docs/premises.md)
- [Project brief](docs/brief.md)
- [Architecture](docs/architecture.md)
- [Lab 1: build on AWS by hand](docs/lab-1-by-hand.md)
- [Lab 2: build on AWS with CloudFormation](docs/lab-2-cloudformation.md)
- [Lab reference: Learner Lab rules, costs, troubleshooting](docs/lab-common.md)
- [Commands: build, switch and delete the portal](docs/commands.md)
- [Test log for the one-stack build](docs/stack-test-log.md)
- [Data model](docs/data-model.md)
- [Decisions](docs/decisions/)
- [Technical debt](docs/technical_debt.md) (the portal's own; each system keeps its own in the portal)
