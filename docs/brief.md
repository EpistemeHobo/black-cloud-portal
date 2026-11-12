# Project brief: Cloud Internal Developer Portal

*Owner: <name> · Backup person: <name> · Date: 2026-10-29 · Status: Draft*

## Problem

Cloud has no single place that lists its apps and systems, who owns them, and how far each one is in its development. Information lives in people's heads, scattered documents and a Google Form inventory. A leader or peer who wants to understand a project has to ask someone to explain it, usually in a meeting. Developers also have to read and remember the whole SOP to know which documents each development step needs.

## Users

| Who | What they need to do |
| --- | --- |
| Developers and trainees | Register their system, see what each step needs, keep the system's page up to date |
| Team leaders | Understand any project before a meeting, and record review notes |
| Peers | Learn how other systems are built and what they depend on |
| IT team | See every system in one place; maintain the checklist items |

## What the app must do

1. Users can sign up and sign in with their work email; an admin approves each account.
2. Users can see a list of every system, and search and filter it by type, step, unit and owner.
3. Users can register a new system, including ones that are not in Git.
4. Owners can edit their system's details, people, links and dependencies.
5. Users can open a system's page and understand it without a meeting: why it exists, where it stands, how it is built and what has been decided.
6. Users can see the checklist for the system's current step, with a link to the knowledge base for each item.
7. Owners can mark checklist items done and add evidence.
8. Owners can move their system to any step; missing items are shown, not enforced.
9. Leaders and peers can add review notes to a system.
10. Users can see what a system depends on and what depends on it.
11. Users can see who changed what on a system, and when.
12. Admins can change the checklist items without a code change.
13. Owners can record their system's technical debt (what, why, impact, plan, risk, target date), and anyone can see it across systems.
14. A system's people can keep its secrets in an encrypted vault that only they can read, instead of in its pages.
15. The portal warns before saving text that looks like a secret, alerts the system's people about every leak it finds (on save and on a schedule), and hides leaked text from everyone else.

## Out of scope

- Showing documentation pages. Explanations and how-tos live in the knowledge base site.
- Replacing team meetings. The portal prepares people for them and records their outcomes.
- Monitoring, alerts, or measuring developer productivity.
- Importing the Google Form inventory (planned for a later version).
- Comments and suggested edits (planned for a later version).

## Limits

- **Data:** names and email addresses of staff; system details, some sensitive (server locations, data storage locations, known vulnerabilities). No patient or research data.
- **Must work on:** current desktop browsers; reachable from the NSTDA internal network only.
- **Other:** the portal's own email-and-password accounts, with email through SMTP (Resend); deployed through the standard pipeline to the team's Kubernetes cluster.

## Existing systems checked

- **The Google Form inventory:** collects system details once, but has no ownership history, steps, checklists or review notes.
- **Backstage, Port, Cortex:** built for large organizations. Backstage keeps its catalog in Git and needs a platform team; Port and Cortex are hosted services outside the internal network.

## How we will know it works

- Every system from the inventory is in the portal, with a technical owner and a backup owner.
- Leaders open a system's page before review meetings instead of asking for an explanation.
