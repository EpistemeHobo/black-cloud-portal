# Technical debt: Cloud Internal Developer Portal

Shortcuts we took on purpose and plan to fix. Add an entry in the same merge request
as the shortcut, and open a GitLab issue with the label `technical-debt`.
When an item is fixed, move it to **Paid off**.

This file is the portal's own debt. Each system in the portal keeps its debt in its
**หนี้ทางเทคนิค** tab, with the same fields.

## Open

### TD-1: No import from the Google Form inventory

*Recorded: 2026-10-29 · Issue: #<number> · Risk: Medium*

**What it is:**
Systems are registered one by one in the portal. The responses already collected by the App & System Inventory form can't be loaded.

**Why we took it on:**
To get the portal working first. The import needs the Status mapping in `data-model.md` and a "needs matching" list for owner names.

**What happens if we leave it:**
Owners re-type what they already gave in the form, and some won't.

**When we plan to fix it:**
Before inviting all units to use the portal.

**How to fix it:**
1. Add `python -m app.import_inventory <responses.csv>`, mapping columns as in `data-model.md`.
2. Put unmatched owner names on a list for the IT team instead of guessing.

Rough effort: 2 days

### TD-2: The checklist items have no new standards version, and no screen to edit them

*Recorded: 2026-10-29 · Issue: #<number> · Risk: Low*

**What it is:**
The portal's checklist page moved to the knowledge base (2026-10-30), so there is no screen to edit items any more; the API (`/api/standards/items/{code}`) can still change one in place. Adding, removing or versioning items needs a change to `standards_v1.json` and a deploy, and the knowledge base page should be updated to match.

**Why we took it on:**
Standards v1 is still a draft; versioning can wait until it is agreed.

**What happens if we leave it:**
A big standards change can't be prepared ahead and switched on at once.

**When we plan to fix it:**
Before Standards v2.

**How to fix it:**
1. Let admins copy the current version into a draft, edit it, then make it current.

Rough effort: 3 days

### TD-3: Comments and suggested edits are not built yet

*Recorded: 2026-10-29 · Issue: #<number> · Risk: Low*

**What it is:**
Peers can add review notes, but can't comment on a specific field or suggest an edit to someone else's system.

**Why we took it on:**
Review notes cover premise 1 for the first version.

**What happens if we leave it:**
Corrections go through the owner by chat or in meetings.

**When we plan to fix it:**
After the first users have tried the portal.

**How to fix it:**
1. Add a `comment` table (system, optional field or checklist item, author, text, resolved).

Rough effort: 3 days

### TD-4: The leak scanner only matches patterns

*Recorded: 2026-11-11 · Issue: #<number> · Risk: Medium*

**What it is:**
`leak_scan.py` finds secrets by regular expression and a simple entropy check. It doesn't ask the provider whether a token is live (GitHub does), doesn't read anything outside the portal (Git history, the linked repositories), and doesn't look inside files other than markdown.

**Why we took it on:**
Checking a token with its provider sends it to an outside service from the internal network, and the portal only stores text and markdown today.

**What happens if we leave it:**
Some false positives in the generic rules (owners close them once), and secret formats without a known prefix (a LINE channel token, an internal API key) slip through unless written as `password = …`.

**When we plan to fix it:**
When owners report more than a few false positives a month, or before the portal accepts other file types.

**How to fix it:**
1. Add rules for the formats owners report, with a test each in `tests/test_security.py`.
2. Consider running `gitleaks` against the source repository links as part of the scheduled scan.

Rough effort: 1 day per batch of rules; 3 days for gitleaks

### TD-5: One encryption key for every vault, kept in an environment variable

*Recorded: 2026-11-11 · Issue: #<number> · Risk: Medium*

**What it is:**
Every system's vault is encrypted with keys derived from one `SECRETS_ENCRYPTION_KEY`, which the app reads from its environment (Secrets Manager or SSM on AWS, the Kubernetes secret on-premises). There is no envelope encryption with KMS and no key per system. Rotation is manual (`python -m app.vault rotate`).

**Why we took it on:**
The on-premises deployment has no KMS, and one key kept outside the database already means a database dump alone gives nothing away.

**What happens if we leave it:**
Anyone who gets both the running container's environment and the database can read every vault. Losing the key loses every vault value.

**When we plan to fix it:**
Before the portal holds production secrets for systems rated Critical.

**How to fix it:**
1. On AWS, encrypt a data key per system with KMS and keep only the encrypted data key in the database.
2. Or move vault values to AWS Secrets Manager or HashiCorp Vault, keeping only a reference in `system_secret`.

Rough effort: 3 days

### TD-6: The scheduled leak scan runs inside the web app

*Recorded: 2026-11-11 · Issue: #<number> · Risk: Low*

**What it is:**
`leak_scan.scheduler()` runs in every app process and scans when the last run is older than `SECRET_SCAN_INTERVAL_HOURS`. With several instances it can run more than once; in hibernate mode it waits until someone wakes the portal.

**Why we took it on:**
No extra service to deploy, on Beanstalk or Kubernetes.

**What happens if we leave it:**
Duplicate work with several instances (harmless), and no scan while the portal sleeps.

**When we plan to fix it:**
When the portal runs on more than one instance, or scans take longer than a minute.

**How to fix it:**
1. Set `SECRET_SCAN_INTERVAL_HOURS=0` and run `python -m app.leak_scan` from a Kubernetes CronJob or an EventBridge schedule.

Rough effort: half a day

### TD-7: Leaked text stays in the change history

*Recorded: 2026-11-11 · Issue: #<number> · Risk: Medium*

**What it is:**
The change history keeps old values as they were. When someone removes a secret from the guide, the old text with the secret is still in `change_log`. It is masked for everyone outside the system, but it is in the database and its backups.

**Why we took it on:**
The history must say who changed what; rewriting it automatically would hide that.

**What happens if we leave it:**
The secret can be read by the system's people, admins, and anyone with a database backup. That's why an alert stays open until the secret is changed at its source.

**When we plan to fix it:**
After the first owners have used leak alerts for a month.

**How to fix it:**
1. Let an owner, from an alert, replace the secret with the mask in that system's history rows, recording that they did.

Rough effort: 2 days

## Paid off

None yet.
