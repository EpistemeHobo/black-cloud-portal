# Commands: build, switch and delete the portal

A short guide to the scripts that control the portal on AWS. [Lab 2](lab-2-cloudformation.md) explains how the pieces work and how to do the same things in the console. Timings are from [real test runs](stack-test-log.md).

| Script | What it does |
| --- | --- |
| `scripts/portal_stack.py` | Builds the whole portal, or deletes all of it |
| `scripts/portal_mode.py` | Switches a portal that already exists between active and hibernate, or wakes it |
| `scripts/build_signin_background.py` | Rebuilds the twinkling dots on Cognito's sign-in page and puts them in the template. Only needed to change their look or speed |

The first two run on **your computer** and send requests to AWS. AWS does the work, so closing the terminal doesn't stop a build or delete. You only lose the progress display.

## Before you start

**Once, on your computer:** install Python 3.10 or newer, get the project, and install the AWS library:

```bash
git clone https://github.com/EpistemeHobo/black-cloud-portal.git
```
```bash
cd black-cloud-portal
```
```bash
python -m pip install boto3
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

Builds everything in about 12 minutes, with your email as the first admin. Check that the session has at least 30 minutes left. When it finishes, it prints the portal's address and the launcher link:

1. Find the email from Cognito with your temporary password. Check the spam folder too.
2. Open the portal's address, press **เข้าสู่ระบบ**, sign in on Cognito's page with your email and that password, and choose a new one. The email's sentence ends with a full stop, which isn't part of the password.

```bash
python scripts/portal_stack.py status
```

Shows whether the stack exists and whether the portal answers.

```bash
python scripts/portal_stack.py delete
```

Removes everything the stack built, in about 11 to 17 minutes. **All portal data and Cognito users are lost:** the users live inside the stack's user pool, so you don't delete them separately, and the next build starts with only your admin. It asks you to type `gargantua` to confirm. Start it with **at least 30 minutes left** in the session. To practise, delete and create again as often as you like.

If the session ended partway, start the lab, copy the new keys and run `delete` again. It finds what was left behind, such as the Beanstalk environment or the user pool, and removes it after you type `remove`. `status` lists them too. If you built those by hand in Lab 1, answer no.

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
| `AWS refused the request: your lab session has ended…` | The lab session ended, or the keys are from an old session | Start the lab, copy the new keys, and run the same command again |
| `ModuleNotFoundError: No module named 'boto3'` | This terminal's Python doesn't have the AWS library, common with Anaconda's `(base)` | `python -m pip install boto3` |
| `Stack gargantua already exists` | It was already built | Use it, or run `delete` first |
| `… doesn't answer: the app failed to start` | The stack built, but the app didn't start | Beanstalk → `cloud-dev` → **Events** and **Logs** |
| `ResourceNotFoundException` … `cloud-dev-portal-mode` from `portal_mode.py` | There's no stack | Run `portal_stack.py create` first |
| `The stack failed` | Building stopped, and everything was removed | CloudFormation → filter **Deleted** stacks → `gargantua` → **Events**; a name conflict with hand-built resources is a common cause |
| Cognito's page says `Incorrect username or password`, or its address doesn't load | See [When something goes wrong](lab-common.md#when-something-goes-wrong) | Most often a full stop copied from the email |
| The portal doesn't answer after a lab restart | The instance may be stuck: see [When a lab session ends](lab-common.md#when-a-lab-session-ends) | Replace the instance, as described there |
