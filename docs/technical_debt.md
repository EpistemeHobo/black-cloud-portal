# Technical debt: Cloud Internal Developer Portal

Shortcuts we took on purpose and plan to fix. Add an entry in the same merge request
as the shortcut, and open a GitLab issue with the label `technical-debt`.
When an item is fixed, move it to **Paid off**.

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

## Paid off

None yet.
