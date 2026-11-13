# 9. Secret boxes, leak scanning and technical debt

*Date: 2026-11-12 · Status: Accepted*

## Context

Developers describe how their systems run, paste commands into the guide and attach runbooks, so a password, token or private key ends up in the portal sooner or later. Every signed-in person can read every system's page, and the change history keeps old text. The "secrets" link kind only points somewhere else; the portal had no safe place for the values themselves, and nothing noticed when one was typed in plain text.

Owners still keep the real copies of their secrets elsewhere, such as a `.env` file kept out of Git or a password manager. What they need from the portal is a second copy that can be handed over with the system, which nobody else, not even the portal's operators, can read.

Teams also take shortcuts on purpose (skipped tests, a manual deploy), and nothing recorded them apart from the portal's own `docs/technical_debt.md`.

## Decision

1. **Secret boxes, encrypted in the browser with keys the portal never receives.** A system can have several boxes (one per environment or integration, say). When someone creates a box, their browser generates a random 256-bit key (`pvk1_…`) and shows it once, to copy or download. Contents are encrypted there with AES-256-GCM, bound to the box and version, and only ciphertext is uploaded. The server stores a key check, so a wrong key gets a clear answer, and the first 8 hex characters of the key's SHA-256, so people can tell keys apart. A database dump, a backup, the server's own settings or an admin can't open a box (`vault.py`, `frontend/src/lib/boxCrypto.ts`).
2. **The portal is a second copy, never the only one.** A lost key can't be recovered, by design. The page says so on every box list, and creating a box or changing its key asks the person to confirm that they've kept the key and still have the original elsewhere.
3. **Keys pass between people, not through the portal.** The box's creator gives the key to whoever takes over, through a password manager's sharing or in person, never by chat or email. A key pasted into any page of the portal is reported as a critical leak.
4. **Every save is a new version;** old versions stay readable with the box's key and can be restored. Two people saving at once can't overwrite each other: a save on top of a version the browser didn't see is refused. Deleting a box deletes every version, for good.
5. **Changing a key** re-encrypts every version in the browser under a new key and replaces them all at once. The box lists people taken off the system since its key last changed, who may still hold the old key.
6. **Only the system's people may download ciphertext:** its business, technical and backup owners and its developers (`enums.SECRET_ROLES`). Admins see names, versions and history, not ciphertext. This is defence in depth: the key is the real lock.
7. **Box events are in the system's history** (created, saved, opened, key changed, deleted), by name, never contents. Those rows are hidden from people outside the system. "Opened" is reported by the browser after the right key opened the box.
8. **Leak scanning in three layers,** as GitHub secret scanning, GitGuardian and Amazon CodeGuru/Macie do:
   - *Push protection:* a save that adds a critical or high-severity finding nobody has seen yet is refused with what was found. The frontend asks once, in `api()`, and saves anyway with `?allow_secrets=true` if the person says it isn't a secret or must stay.
   - *Scan on save:* everything saved is scanned and becomes an alert for the system's people, who are emailed (not the person who saved).
   - *Scheduled scan:* every `SECRET_SCAN_INTERVAL_HOURS` (24 by default) every system is scanned again, attached files included, so new rules catch old text. `python -m app.leak_scan` runs the same scan from a cron job.
9. **What is detected:** known token formats (AWS, Google, Azure, GitHub, GitLab, Slack, Stripe, OpenAI, Anthropic, Hugging Face, SendGrid, Resend, npm, Telegram), the portal's own box keys, private keys, JWTs, passwords in connection URLs and bearer headers, and generic `password = …` assignments filtered for placeholders and low-entropy words. The parts of a box that are not encrypted (name, description, version notes) are scanned too. A line with `portal:ignore-secret` is skipped, for documented example values.
10. **The scanner never stores a secret.** An alert keeps an HMAC-SHA256 fingerprint and a masked preview such as `ghp_…Zq`. The fingerprint key is derived from `JWT_SECRET_KEY` when it is set, otherwise from a key file next to the database, so a short password can't be brute-forced from the database alone.
11. **Text that looks like a secret is masked for everyone outside the system** (detail page, systems list, dashboard, reviews, checklist evidence, history, the debt list) until an owner closes the alert as "not a secret" or "test value". A masked copy can't be saved back over the real text.
12. **An alert stays open until someone closes it with a reason** (revoked, moved to a box, not a secret, test value, accepted risk), even after the text is edited out: the old text is still in the history and in anyone's copy, so the secret must be changed at its source.
13. **Technical debt per system,** with the same fields as `docs/technical_debt.md` (what, why, impact, fix, risk, effort, target date, issue link, status). Everyone can read it; the system's editors keep it. Overdue high-risk debt and open serious leak alerts appear on the dashboard.

## Options considered

- **A server-held key (built first, never released):** values encrypted with one `SECRETS_ENCRYPTION_KEY` from the environment. Anyone with both the running app's environment and the database could read every system's secrets, and admins could in principle. Replaced by this decision.
- **A key per person, with each box's key wrapped for every member (as 1Password and Bitwarden organisations do):** handover inside the portal, and removing one person without changing the key. Needs key pairs and recovery for every person, more than a second copy needs (technical debt TD-5).
- **AWS Secrets Manager or HashiCorp Vault:** a dependency the on-premises deployment doesn't have, and the operators could still read the values.
- **Only warn, never refuse a save:** by the time the alert arrives the secret is in the history. Refusing first, with a one-click override, matches GitHub's push protection.
- **Hide whole fields from non-members:** would hide most of the guide, which premise 1 wants open. Masking only the secret keeps the page readable.
- **Checking whether a found token is live with its provider (as GitHub does):** sends secrets to outside services from the internal network; left out.

## Consequences

- A lost box key loses the box. That's acceptable only because the original lives elsewhere, which the page keeps saying.
- Boxes need HTTPS (or localhost): browsers offer Web Crypto only in a secure context. The page says so when it isn't.
- The server delivers the JavaScript that does the encryption, so a compromised server could ship code that steals keys as they are typed. Every web-based vault has this limit.
- The scanner can no longer recognise a box's values pasted in plain text elsewhere, because the server can't read the boxes. It still catches them when they match a known format.
- Generic rules give false positives; owners close them once and the text is shown again everywhere on that system.
- Every instance runs the scheduled scan; with several instances it runs more than once, which is harmless.
- Changing `JWT_SECRET_KEY` changes every fingerprint, so known leaks are reported once more.
