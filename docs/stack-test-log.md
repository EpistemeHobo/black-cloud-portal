# Test log: `infra/full-stack.yaml`

Real runs in an AWS Academy Learner Lab account, region us-east-1, on 2026-11-02. Times are Thai time (UTC+7). Durations come from the timestamps the commands printed; steps logged only to the minute are marked `~`. Timings will vary from account to account.

## Summary

| What | Measured |
| --- | --- |
| Build everything (stack start to portal answering) | **about 12 minutes** (4 builds: 12, 12, 12, 12) |
| Delete everything, Aurora running | **about 11 to 14 minutes** |
| Delete everything, Aurora asleep | **about 17 minutes** (it wakes Aurora first) |
| Switch to hibernate until Aurora is stopped | **about 5½ to 7½ minutes** |
| Wake from asleep until the portal answers | **about 5 minutes** |

Inside the final build: database cluster 36 s, database instance 5 min 9 s, Beanstalk environment 5 min 36 s.

## Every step, in order

| # | Step | Start | End | Duration | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | Delete the hand-built resources (by CLI) | 12:10 | 12:33 | ~23 min | Pass, nothing left |
| 2 | Build, first attempt | 12:33 | 12:40 | ~7 min | **Fail:** Beanstalk couldn't find the security group: no VPC given |
| 3 | Delete the failed stack | 12:40 | 12:47 | ~7 min | Pass, nothing left |
| 4 | Build with the VPC fix | 12:47 | 12:59 | ~12 min | **Fail:** `CREATE_COMPLETE`, but the app crashed: files in the code bundle were readable by root only |
| 5 | Delete | 13:04 | 13:18 | ~14 min | Pass, nothing left |
| 6 | Build with the permissions fix | 13:18 | 13:30 | ~12 min | Pass, HTTPS answered at once |
| 7 | Check the running portal (see below) | 13:30 | 13:32 | ~2 min | Pass |
| 8 | Switch to hibernate | 13:32:12 | 13:37:43 | 5 min 31 s | Pass: Aurora stopped, 0 instances, launcher showed the waking-up page |
| 9 | Wake, as the waking-up page does | 13:38:00 | 13:43:09 | 5 min 9 s | Pass: launcher forwards, home page 200 |
| 10 | Switch to hibernate | 13:43:39 | 13:49:55 | 6 min 16 s | Pass |
| 11 | Delete with Aurora stopped | 13:50:01 | 13:53:41 | 3 min 40 s | **Fail:** `Db cluster portal-db is in stopped state` |
| 12 | Start Aurora by hand, to clear the failed delete | 13:54:52 | 14:00:16 | 5 min 24 s | Pass |
| 13 | Delete again | 14:00 | 14:11 | ~11 min | Pass, nothing left |
| 14 | Build with the wake-before-delete fix (script) | 14:12:11 | 14:24:04 | ~12 min | Pass |
| 15 | Switch to hibernate | 14:24:04 | 14:31:43 | 7 min 39 s | Pass |
| 16 | Delete with Aurora stopped (script) | 14:31:43 | 14:48:52 | ~17 min | **Pass,** nothing left: the case that failed in step 11 |
| 17 | Final build (script) | 14:49:11 | 15:01:10 | 11 min 59 s | Pass, portal answering, `"ready": true` |

"Nothing left" means: no docs bucket, database, security groups, secrets or functions. From step 13 on, the parameter `/cloud-dev-portal/woken-at` remains, since the function creates it itself rather than the stack; it's harmless, and the next build reuses it. Beanstalk's own bucket also remains.

## What step 7 checked

| Check | Result |
| --- | --- |
| HTTPS home page, title "Gargantua Internal Developer Portal" | 200 |
| `/systems` redirect stays on the HTTPS address | Yes |
| `/launch` when awake | 302 to the portal |
| Beanstalk address, visited directly | 403 |
| Beanstalk address with a forged `X-Origin-Verify` header | 403 |
| `/api/health` directly (needed by the mode function) | 200 |
| Plain-HTTP request to the S3 bucket | 403 |
| Instance key pair, and open ports | None; only port 80 |
| Database user the app runs as | `portal_app` on `portal`, not a superuser |
| Admin account and checklist items in the database | 1 and 23 |
| App writes, reads and deletes an S3 object | Yes |

## Not tested

- **Signing in through a browser,** and attaching a `.md` file through the portal's pages. Step 7 tested S3 from inside the app's container, not through the page.
- **The idle check and the midnight rule firing by themselves.** Steps 8 and 15 sent the same `hibernate` message by hand. The idle decision has unit tests only.
- **A lab session ending with the stack in place,** including whether `LabRole` works with no session open.
