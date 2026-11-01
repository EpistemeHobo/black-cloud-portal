# 3. The system page is a handover guide

*Date: 2026-10-29 · Status: Accepted*

## Context

The v1 system page was built for review: a Journey tab, a long Details form copied from the inventory, a standards checklist and people and links. Developers were asked to fill in all of it, including cost, contracts and security fields that don't help anyone run the system.

The real need is **inheriting**: trainees and juniors take systems over from seniors, and they need to run and change them safely without a meeting.

## Decision

1. **The system page is a handover guide** built on seven questions (see `docs/handover-guide.md`). It is the default view and reads top to bottom with no tabs.
2. **Developers are asked to answer only those seven questions.** Progress counts answered questions, not fields.
3. **Catalog details move to a separate Catalog info form**, filled in by audit or IT staff (a new *auditor* flag) or admins. Developers may edit it but are never prompted to.
4. **Overlapping fields move into the guide:** description, business purpose, known issues and roadmap notes.
5. **Review notes stay** as a section below the guide.
6. **The standards checklist and the 7 development steps become an optional tab** below the guide, mainly for new projects. They are not counted in the guide's progress and nobody is prompted to fill them.

## Options considered

- Keep the review-first page and add a handover tab: the developer would still face the full form, and readers would still have to hunt across tabs.
- Drop the catalog fields entirely: the inventory still needs them for audit, so they move rather than go.

## Consequences

- New data: three run/deploy/roll-back step fields and an *if down* field on System, two new tables (watch-out items and open items), new link kinds (logs, dashboard), and *reachable until* and *note* on a system role. See `docs/data-model.md`.
- Premise 1 is reworded and premise 2 is added (`docs/premises.md`).
