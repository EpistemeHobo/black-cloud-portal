# 9. Secrets vault, leak scanning and technical debt

*Date: 2026-11-11 · Status: Accepted*

## Context

Developers describe how their systems run, paste commands into the guide and attach runbooks, so a password, token or private key ends up in the portal sooner or later. Every signed-in person can read every system's page, and the change history keeps old text. The "secrets" link kind only points somewhere else; the portal had no safe place for the values themselves, and nothing noticed when one was typed in plain text.

Teams also take shortcuts on purpose (skipped tests, a manual deploy), and nothing recorded them apart from the portal's own `docs/technical_debt.md`.

## Decision

1. **A secrets vault per system.** Values are encrypted with Fernet (AES-128-CBC plus HMAC-SHA256) under a key derived from `SECRETS_ENCRYPTION_KEY`, which lives outside the database: Secrets Manager in the CloudFormation stack, SSM Parameter Store by hand, the Kubernetes secret on-premises. The database holds only ciphertext, and nothing about the value (not even its length) in clear.
2. **Only the system's people read values:** its business, technical and backup owners and its developers (`enums.SECRET_ROLES`), the people who build it and the one who takes it over. Admins see the names and the alerts, not the values; an admin who needs a value adds themself to the system, which its history records. Auditors, support contacts, previous owners and everyone else see neither. Removing someone from the system removes their access at once.
3. **Every reveal, change and removal** is in the system's history by name, never the value. Those rows are hidden from people outside the system.
4. **Leak scanning in three layers,** as GitHub secret scanning, GitGuardian and Amazon CodeGuru/Macie do:
   - *Push protection:* a save that adds a critical or high-severity finding nobody has seen yet is refused with what was found. The frontend asks once, in `api()`, and saves anyway with `?allow_secrets=true` if the person says it isn't a secret or must stay.
   - *Scan on save:* everything saved is scanned and becomes an alert for the system's people, who are emailed (not the person who saved).
   - *Scheduled scan:* every `SECRET_SCAN_INTERVAL_HOURS` (24 by default) every system is scanned again, attached files included, so new rules catch old text. `python -m app.leak_scan` runs the same scan from a cron job.
5. **What is detected:** known token formats (AWS, Google, Azure, GitHub, GitLab, Slack, Stripe, OpenAI, Anthropic, Hugging Face, SendGrid, Resend, npm, Telegram), private keys, JWTs, passwords in connection URLs and bearer headers, and generic `password = …` assignments filtered for placeholders and low-entropy words. Any value from the system's own vault found in plain text is critical. A line with `portal:ignore-secret` is skipped, for documented example values.
6. **The secret is never stored by the scanner.** An alert keeps an HMAC-SHA256 fingerprint (keyed from the vault key, so a short password can't be brute-forced from the database alone) and a masked preview such as `ghp_…Zq`.
7. **Text that looks like a secret is masked for everyone outside the system** (detail page, reviews, checklist evidence, history, the debt list) until an owner closes the alert as "not a secret" or "test value". A masked copy can't be saved back over the real text.
8. **An alert stays open until someone closes it with a reason** (revoked, moved to the vault, not a secret, test value, accepted risk), even after the text is edited out: the old text is still in the history and in anyone's copy, so the secret must be changed at its source.
9. **Technical debt per system,** with the same fields as `docs/technical_debt.md` (what, why, impact, fix, risk, effort, target date, issue link, status). Everyone can read it; the system's editors keep it. Overdue high-risk debt and open serious leak alerts appear on the dashboard.

## Options considered

- **AWS Secrets Manager or Vault (HashiCorp) per secret:** stronger isolation and audit, but a dependency the on-premises deployment doesn't have, and a cost per secret. The vault stores ciphertext the same way, so values can move there later (technical debt TD-5).
- **Only warn, never refuse a save:** simpler, but by the time the alert arrives the secret is in the history. Refusing first, with a one-click override, matches GitHub's push protection.
- **Hide whole fields from non-members:** would hide most of the guide, which premise 1 wants open. Masking only the secret keeps the page readable.
- **Delete leaked text from the history automatically:** would rewrite who-changed-what; the history stays complete and masked instead (TD-7).
- **Checking whether a found token is live with its provider (as GitHub does):** sends secrets to outside services from the internal network; left out.

## Consequences

- Losing `SECRETS_ENCRYPTION_KEY` loses every vault value. The stack keeps its key secret when deleted; on-premises it must be backed up with the database backups.
- With PostgreSQL and no key, the vault is off (503) rather than encrypt with a key a redeploy would lose. With SQLite and no key, a key file is made next to the database.
- Generic rules give false positives; owners close them once and the text is shown again everywhere on that system.
- Every instance runs the scheduled scan; with several instances it runs more than once, which is harmless.
