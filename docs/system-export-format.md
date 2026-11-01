# System export format

*Version 1 · Last updated: 2026-10-29*
*Code: `backend/app/transfer.py` (export and import), `frontend/src/lib/systemFolder.ts` (reading a folder or .zip)*

A system can be exported as a folder and imported again as a **new** system, on this portal or another one.

## Folder layout

```
APP-003-cohort-builder/
├── system.json            everything that goes into the database
├── README.md              what the folder is and how to import it
└── docs/                  markdown files attached to the handover guide
    ├── 1-what/
    ├── 2-where/
    ├── 3-how/runbook.md
    ├── 4-watch/
    ├── 5-deps/
    ├── 6-who/
    └── 7-progress/
```

Only folders that hold files are written. A browser can only download one file, so the export arrives as `APP-003-cohort-builder.zip` holding that folder.

## system.json

| Key | Holds |
|---|---|
| `format`, `version` | Always `t2gen-dev-portal/system` and `1`. Import refuses other formats and newer versions |
| `exported_at`, `exported_from` | When, and the original system ID (for reference only) |
| `system` | `name`, `type`, `lifecycle_state`, `step` |
| `owning_unit` | Unit name, or `null` |
| `guide` | `description`, `if_down`, `run_steps`, `deploy_steps`, `rollback_steps`, and `nothing` (questions marked "nothing to list") |
| `catalog` | Every catalog field, confidential ones included |
| `people` | `name`, `email`, `role`, `reachable_until`, `note` |
| `links`, `watch_outs`, `open_items` | As on the system page, without database IDs |
| `dependencies` | `system_id`, `name`, `external`, `note` |
| `checklist` | `code`, `status`, `evidence` for answered checklist items |

The `.md` files are not inside `system.json`. They are read from `docs/<number>-<question>/`. A folder named `3-how`, `how` or `3` all mean question 3. Files elsewhere are skipped, and the import screen lists them.

## Rules

- **Export:** owners, developers and admins only, because the file includes confidential catalog fields.
- **Import:** any signed-in person. The system gets a new ID, and the importer becomes a technical owner.
- **People** are matched by email. Unknown emails become new people records, as when an owner adds someone who hasn't signed in.
- **Units** are matched by name and created if missing.
- **Dependencies** link to a system in this portal when the original ID still has the same name, or when exactly one system has that name. Otherwise they become external names.
- **Not carried over:** review notes and change history. They belong to the original system's record.
- **Limits:** 100 `.md` files, each up to 200,000 characters. The browser ignores files over 1 MB and archives with more than 200 files.
