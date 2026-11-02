# Commands: build, switch and delete the portal

A short guide to the two scripts that control the portal on AWS. [Lab 2](lab-2-cloudformation.md) explains how the pieces work and how to do the same things in the console. Timings are from [real test runs](stack-test-log.md).

| Script | What it does |
| --- | --- |
| `scripts/portal_stack.py` | Builds the whole portal, or deletes all of it |
| `scripts/portal_mode.py` | Switches a portal that already exists between active and hibernate, or wakes it |

Both run on **your computer** and send requests to AWS. AWS does the work, so closing the terminal doesn't stop a build or delete. You only lose the progress display.

## Before you start

**Once, on your computer:** install Python 3.10 or newer, get the project, and install the AWS library:

```bash
git clone https://github.com/EpistemeHobo/black-cloud-portal.git
```
```bash
cd black-cloud-portal
```
```bash
pip install boto3
```

**Every lab session**, because the keys change each time:

1. On the Learner Lab page, press **Start Lab** and wait for the green dot.
2. **AWS Details** → **AWS CLI: Show** → copy the whole block.
3. Paste it over everything in `~/.aws/credentials` and save. On Windows that's `C:\Users\<you>\.aws\credentials`.

Run the commands from the project folder, in any terminal: PowerShell, the VS Code terminal, or Terminal on a Mac.

## Build, check, delete

```bash
python scripts/portal_stack.py create you@example.org
```

Builds everything in about 12 minutes, with your email as the first admin. Check that the session has at least 30 minutes left. When it finishes, it prints the portal's address, the launcher link, and where to find the password:

1. Console → **Secrets Manager** → open the secret it names → **Retrieve secret value**.
2. Open the portal's address and sign in with your email and that password.

```bash
python scripts/portal_stack.py status
```

Shows whether the stack exists and whether the portal answers.

```bash
python scripts/portal_stack.py delete
```

Removes everything the stack built, in about 11 to 17 minutes. **All portal data is lost.** It asks you to type `gargantua` to confirm. To practise, delete and create again as often as you like.

## Switch modes

These need the stack to exist.

```bash
python scripts/portal_mode.py active
```

For presentation days: starts everything and keeps it on. Run it at least 15 minutes before you start.

```bash
python scripts/portal_mode.py hibernate
```

For development days, and **before a lab session ends**: stops Aurora and the instance now. They wake when someone opens the launcher link, and sleep again after 30 minutes without visitors.

```bash
python scripts/portal_mode.py wake
```

Starts everything now without leaving hibernate mode, so it goes back to sleep when unused.

```bash
python scripts/portal_mode.py status
```

Shows the mode and what's running. Everything is up when `"ready"` is `true`.

## A typical day

**Practising the build:**

| When | Do |
| --- | --- |
| Start | Start the lab, refresh the keys, run `portal_stack.py create you@example.org` |
| Practise | Use the portal |
| Finish | Run `portal_stack.py delete` before the session ends. It stops all costs except a little S3 storage in Beanstalk's own bucket |

**Keeping the portal between sessions:**

| When | Do |
| --- | --- |
| Start | Start the lab, refresh the keys, open the launcher link and wait on the waking-up page |
| Finish | Run `portal_mode.py hibernate` before the session ends |

**Presentation day:**

| When | Do |
| --- | --- |
| 15 minutes before | `portal_mode.py active`, then wait until `status` says `"ready": true` |
| After | `portal_mode.py hibernate` |

## Costs

Aurora and the instance cost about **$2.50 a day while running**, even with no lab session open. They stop costing when you run `hibernate` or `delete`, apart from small storage charges. A stopped Aurora restarts by itself after 7 days, so run `hibernate` again if you haven't been back for a week.

## When a command fails

| Message | What it means | Do this |
| --- | --- | --- |
| `explicit deny` … `voc-cancel-cred` | The lab session ended, or the keys are from an old session | Start the lab and copy the new keys |
| `Unable to locate credentials` | No keys saved | Do "Every lab session" above |
| `Stack gargantua already exists` | It was already built | Use it, or run `delete` first |
| `… doesn't answer: the app failed to start` | The stack built, but the app didn't start | Beanstalk → `cloud-dev` → **Events** and **Logs** |
| `ResourceNotFoundException` … `cloud-dev-portal-mode` from `portal_mode.py` | There's no stack | Run `portal_stack.py create` first |
| `The stack failed` | Building stopped, and everything was removed | CloudFormation → filter **Deleted** stacks → `gargantua` → **Events**; a name conflict with hand-built resources is a common cause |
| The portal doesn't answer after a lab restart | The instance may be stuck: see [When a lab session ends](lab-common.md#when-a-lab-session-ends) | Replace the instance, as described there |
