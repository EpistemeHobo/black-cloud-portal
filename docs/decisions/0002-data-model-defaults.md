# 2. Data model choices for v1

*Date: 2026-10-29 · Status: Proposed*

## Context

The data model left five questions open. The portal needs an answer to each before the first version is built.

## Decision

1. **Steps and lifecycle state are separate fields.** `step` (1 to 7) says how far development has gone. `lifecycle_state` (Active, Maintenance-only, Deprecated, Retired) says what happens to the system now. Systems already in production start at step 6, with their missing items showing.
2. **No components in v1.** One record per system. Parts (frontend, API, database) can be added later if teams ask for them.
3. **Confidential fields are hidden from most users.** Server or location, data storage location, backup details and known vulnerabilities are shown only to the system's owners, developers and admins.
4. **Owners, developers and admins edit a system.** Everyone else can read it and add review notes.
5. **No separate "legacy" checklist.** Older systems use the same checklist. Items that don't fit are marked Not applicable, with a reason.

## Options considered

- A single Status field (as in the inventory form): mixes development progress with what happens after go-live.
- Anyone can edit, with changes reviewed: more open, but needs a review workflow that v1 doesn't have.

## Consequences

- Importing the inventory needs the Status mapping in `data-model.md`.
- Checklist pages for older systems will show many missing items at first.
