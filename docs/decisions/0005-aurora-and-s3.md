# 5. Aurora PostgreSQL for data, S3 for attached files

*Date: 2026-11-01 · Status: Accepted*

## Context

The portal is deployed on AWS (Elastic Beanstalk, AWS Academy Learner Lab) as a cloud class project. SQLite on a container volume doesn't survive an instance being replaced and can't be shared by more than one instance. The markdown files attached to the handover guide were stored as text in the `guide_doc` table.

## Decision

1. **Structured data goes to Aurora PostgreSQL.** The app takes the address as `DATABASE_URL` or in parts (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, …). SQLite stays the default for development and tests.
2. **Migrations and seeding hold a PostgreSQL advisory lock**, so containers starting together don't run them twice.
3. **Attached files go to S3** when `DOCS_BUCKET` is set: one object per file at `systems/<id>/<question>/<file>`. The row keeps the key and a SHA-256 of the text. The bucket is private and versioned, so replaced and removed files can be recovered.
4. **The API is unchanged**: the backend reads the file from S3 and returns its text as before, caching it per instance by key and checksum. Objects are deleted only after the database commit.
5. **Credentials come from the instance profile** (LabInstanceProfile in Learner Lab); no AWS keys in settings.

## Options considered

- **Keep files in the database:** simpler, but the project brief asks for S3, and versioning in S3 gives file history for free.
- **Presigned URLs, browser fetches from S3:** fewer bytes through the app, but the frontend would change and the bucket would need CORS. Files are small (under the upload limit), so the app passes them through.

## Consequences

- `python -m app.doc_store` moves files still kept in the database into S3, once, after `DOCS_BUCKET` is set.
- Copying an existing SQLite portal's data into Aurora is not automated; a new deployment starts empty (or with `python -m app.seed --demo`).
