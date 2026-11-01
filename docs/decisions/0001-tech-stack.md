# 1. Tech stack: FastAPI + Next.js, as in Cohort Builder

*Date: 2026-10-29 · Status: Accepted. Sign-in changed by [decision 0004](0004-own-accounts.md): own accounts instead of Keycloak SSO.*

## Context

The portal lists every Cloud system and guides developers through the development steps. About 50 users, small amounts of data, login through SSO, internal network only. Cloud has no fixed tech stack; each project chooses one and writes down why.

## Decision

Python 3.11 (FastAPI, SQLAlchemy, Alembic) backend and Next.js (React, PrimeReact, Tailwind) static frontend, in one Docker container. SQLite database. Keycloak SSO. Deployed to Kubernetes through GitLab CI. This is the Cohort Builder stack, plus SQLAlchemy and Alembic.

## Reasons

- **Fits the task:** forms, tables and checklists; the data is small enough for SQLite.
- **Who can maintain it:** the developer and the Kubernetes deployer already run Cohort Builder on this stack.
- **Can be deployed:** the same pipeline and Kubernetes layout as Cohort Builder. Deployer confirmation: <name>, <date>.
- **Cost and licences:** all open source, no cost.

## Options considered

- **Django + PostgreSQL:** good built-in admin pages, but nobody on the team runs Django yet.
- **Backstage:** built for large organizations, keeps its catalog in Git, and needs a platform team.
- **Port or Cortex:** hosted services outside the internal network.

## Consequences

- Cohort Builder's SSO code and pipeline can be reused.
- SQLAlchemy and Alembic add a migration step that Cohort Builder doesn't have, so table changes are safe and repeatable.
- SQLite allows only one running copy of the app, and needs a nightly backup job.
