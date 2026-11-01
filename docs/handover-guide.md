# Handover guide: design

*Version 0.1 · Last updated: 2026-10-29*
*Why: [premises](premises.md) · Decision: [0003](decisions/0003-handover-first.md)*

Each system's page in the portal is a **handover guide**: everything the next owner needs to take the system over without a meeting. The developer answers seven questions, and only those. Catalog details for audit live in a separate form (see [Catalog info](#catalog-info-separate-from-the-guide)).

## The seven questions

| # | Question (as shown) | What the writer fills in | How the reader sees it |
|---|---|---|---|
| 1 | What is it, and what breaks if it's down? | Two short boxes: *What it does* (1–2 sentences) and *If it's down* (who notices, how fast) | A summary at the top of the page. *If it's down* sits in a highlighted box |
| 2 | Where is everything? | Links. Paste a URL and the kind is guessed (a GitLab URL becomes Source repo). Quick-add buttons for the common kinds | A row of link buttons under the summary: Repo · Production · Logs · Dashboard · Docs |
| 3 | How do I run, deploy and roll it back? | Three boxes: *Run locally*, *Deploy*, *Roll back*. One step per line. A line in `backticks` is a command | Numbered steps. Commands get a copy button |
| 4 | What will bite me? | A list. Each item is a **trap** ("don't restart the worker during a nightly import") or a **chore** ("renew the TLS certificate", how often, next due date) | Traps as a warning list. Chores sorted by next due date, overdue ones in red |
| 5 | What does it depend on, and what uses it? | Pick systems from the catalog, or type a name for something outside it. *Used by* fills itself in | Two lists, linked to those systems' pages |
| 6 | Who do I ask? | People and roles. A **previous owner** has a *reachable until* date and an optional note ("ask about the billing part") | People cards. A previous owner past their date is greyed out |
| 7 | What's in progress? | A list. Each item is **unfinished work**, a **promise** (to whom, by when) or an **open decision**. Tick it when it's finished | Open items first. Finished ones fold away |

Steps 3, 4 and 7 are short lists rather than one big text box. Lists are quicker to scan, and each item can be ticked, dated or sorted.

## Attached markdown files

Every question also accepts `.md` files the developer already has or wants to share, such as a `runbook.md` for question 3. They are context documents about this system. Standards and SOP pages stay in the knowledge base and are only linked.

- **Writer:** use *Attach .md* or drag the file onto the question. Several files per question are allowed, and uploading the same file name again replaces it. A file on its own counts as an answer.
- **Reader:** each file is shown rendered (headings, tables, task lists, highlighted code with a copy button) and can be downloaded. Long files start folded.
- **Safety:** raw HTML in a file is shown as text, and unsafe links are dropped. Files are limited to 200,000 characters.

## Reader side

- **One scrolling page, no tabs for the guide.** The seven questions appear in order. On wide screens a table of contents stays on the left, with a tick next to each question that has an answer.
- **The first screen answers the basics:** name, *what it does*, *if it's down*, link buttons, and the current owner with a "who to ask" shortcut.
- **Unanswered questions stay visible:** "Not written yet. Ask *Somchai* (technical owner)." The reader knows who to ask, and the writer sees the gap.
- **Freshness per question:** "Updated 4 months ago by Tong", taken from the change history. The reader can judge whether to trust it.
- Catalog info, Checklist and History move to tabs or links below the guide. They are not part of the reading path.

## Writer side

- **Edit in place.** Each question is a card with an *Edit* button. The edit form has the same shape as what readers see, so there is no separate form to learn.
- **Every card shows a hint and an example.** For example, *If it's down*: "e.g. Lab staff can't book the sequencer; they notice within an hour."
- **Saves per card.** Writers can fill one question today and the rest next week. Nothing is lost.
- **Progress counts questions, not fields:** "5 of 7 answered". A question counts as answered when its main box or list has something in it. Question 6 needs at least one technical owner.
- **Creating a system asks only for name, type and question 1.** Everything else can wait.
- **Nudges, not blocks.** The dashboard lists the writer's systems with unanswered questions, overdue chores and previous owners whose date has passed. Nothing stops a save.

## Catalog info (separate from the guide)

The rest of the inventory fields (users and criticality, hosting details, data and security, cost and contracts) move to a **Catalog info** form. Audit or IT staff fill it in. Developers may, but they are never asked to.

- A new person flag, **auditor**, lets someone edit catalog info on any system. Admins can already do this.
- Fields that overlap the guide move into it:

| Old field | Goes to |
|---|---|
| `description` | Q1 *What it does* |
| `business_purpose` | Q1 *If it's down* (the old text is copied in as a starting point) |
| `known_issues` | Q4, as traps |
| `roadmap_notes` | Q7, as unfinished work |

- The Catalog info page shows its own progress for auditors only. It is never shown as a gap in the developer's guide.

## Not in this version

- A **Handover** record (from whom, to whom, dates, a sign-off checklist). Add it once the guide is in use and a real handover shows what's needed.
- Per-project agent prompts, comments and suggested edits (phase 4).
