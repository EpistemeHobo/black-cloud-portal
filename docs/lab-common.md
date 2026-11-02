# Lab reference: AWS Academy Learner Lab

Shared by both labs: [Lab 1, by hand](lab-1-by-hand.md) and [Lab 2, CloudFormation](lab-2-cloudformation.md). Read the first two sections before you start either one.

## Rules of the Learner Lab

- Work in **us-east-1** (N. Virginia). Other regions are blocked.
- You can't create IAM roles. Wherever AWS asks for a role, pick **LabRole**; for EC2 it's **LabInstanceProfile**.
- A session lasts 4 hours, and its end needs some care: see the next section.
- Watch the budget shown on the lab page. Aurora costs the most: see [Costs](#costs).
- **CloudFront and Aurora Serverless are blocked.** The labs use API Gateway and a provisioned `db.t3.medium` instead.
- **Cognito works,** including its sign-in pages and built-in email, within its limit of 50 emails a day.

Start the lab, wait for the dot to turn green, then click **AWS** to open the console. Check the region in the top-right corner says N. Virginia.

## When a lab session ends

What happens when a session ends matters more than it looks:

- **Your keys and console tabs stop working.** Every call fails with `explicit deny … voc-cancel-cred`.
- **The instance is lost and replaced, and the replacement can be left without the app.** We saw this happen: the session ended, Beanstalk's instance group launched a new instance, and that instance got `403` from S3 every hour, so it never installed the app. It kept running, and billing, with nothing on it. It didn't recover by itself after the lab restarted.
- **Beanstalk still shows Green,** because Basic health only checks that the instance is alive. Check the portal's address, not the colour.
- **Aurora keeps running and billing.**
- **Anything in progress can stop partway.** CloudFormation works with your session's permissions. We started a stack delete about 2 minutes before the end: Beanstalk's part failed with `not authorized`, the rest carried on, and the stack disappeared and looked done while its Beanstalk environment, application and a `DELETE_FAILED` stack stayed behind. So **start a build or delete with at least 30 minutes left**, and [check afterwards](#if-a-delete-was-cut-off).
- **`LabRole` appears to be blocked too** while the session is off, as those 403s suggest. So don't count on anything that uses it, such as the midnight rule and the idle check, to run with no session open. (Not tested directly for the Lambda function.)

**Before the session ends** (the lab page shows the time left), do one of these:

- Once the hibernate system exists, run the `hibernate` switch. It stops Aurora and sets the instance count to 0, so no replacement is launched.
- In Lab 2, you can delete the stack instead.
- Before the hibernate system exists, stop Aurora: RDS → `portal-db` → **Actions → Stop temporarily**.

**After starting the lab again:**

1. Wait for the green dot, then open the console **from the lab page**. A tab left open from the last session keeps showing `voc-cancel-cred` errors.
2. Copy the new keys into `~/.aws/credentials` if you use the CLI ([how](#using-the-aws-cli-from-your-computer)).
3. Start Aurora if it's stopped, and wait for **Available**. With the hibernate system, opening the launcher link does this for you.
4. Open the portal's address. If it doesn't answer (connection refused or reset) while Beanstalk shows Green, the instance is stuck. **Redeploying doesn't help:** the deploy reports success in seconds, because the instance never finished its first setup. **Replace the instance:** EC2 → Instances → select the environment's instance → **Instance state → Terminate**. It holds no data (that's in Aurora and S3). The group launches a new one, which installs the app from scratch in about 5 minutes. Or from the terminal:

```bash
aws autoscaling terminate-instance-in-auto-scaling-group --instance-id <instance id> --no-should-decrement-desired-capacity
```

If Session Manager can't reach a running instance after a restart, its agent may have failed to register during boot: **Reboot** the instance, or replace it the same way.

### If a delete was cut off

Start the lab, copy the new keys, and look: CloudFormation for a red `awseb-…` stack or `gargantua` in `DELETE_FAILED`, Elastic Beanstalk for an environment `cloud-dev`, and Cognito for a user pool `cloud-dev-portal`. If `gargantua` is still `DELETE_IN_PROGRESS`, wait for it. Then:

```bash
python scripts/portal_stack.py delete
```

It deletes the stack if it's still there, then lists any leftovers and removes them after you confirm. In the console, the same is:

1. Elastic Beanstalk → environment `cloud-dev` → **Actions → Terminate environment**. The `awseb-…` stack goes with it. This took under a minute with no instance left.
2. Elastic Beanstalk → **Applications** → delete `cloud-dev-portal`.
3. If `gargantua` or an `awseb-…` stack still shows `DELETE_FAILED`: select it → **Delete** again.
4. Cognito → user pool `cloud-dev-portal`, if it's still there: delete its domain, then the pool. Its users go with it.

## Costs

- **Aurora and the instance cost about $2.50 a day while running,** even with no lab session open. Aurora is about $0.08 an hour: left on, it alone uses up a $50 budget in under a month.
- **Stopped Aurora costs only storage.** RDS → the cluster `portal-db` → **Actions → Stop temporarily**; **Actions → Start** when you're back, then wait about 5 minutes for **Available**.
- **AWS starts a stopped cluster again by itself after 7 days:** stop it again if you haven't worked on the project for a week.
- **Single-instance Beanstalk** avoids paying for a load balancer.
- **Never create a NAT Gateway:** it bills by the hour and isn't needed here.
- **Cognito** costs nothing at this scale: its free tier covers thousands of monthly users. A pool costs nothing while nobody signs in.
- **API Gateway, Lambda, EventBridge and SSM** cost cents a month at this scale. Each secret in Secrets Manager (Lab 2) is $0.40 a month, charged only for the time it exists.

## Tags

Give every resource the same tags, so they can be listed together (Resource Groups & Tag Editor → filter on `Project`). Keys and values are case-sensitive.

| Key | Value |
| --- | --- |
| `Project` | `cloud-dev-portal` |
| `Name` | the resource's own name, e.g. `portal-db-sg` (security groups show it in the Name column) |
| `Environment` | `dev` |

Beanstalk copies its tags to the EC2 instance and the other resources it creates. Leave out `Name` there: Beanstalk reserves it and sets it to the environment's name ("Tag key 'Name' is reserved").

## Using the AWS CLI from your computer

Lab page → **AWS Details → AWS CLI: Show** → copy the block over everything in `~/.aws/credentials` (on Windows, `C:\Users\<you>\.aws\credentials`) and save. The keys change every session; copy them again each time. A Notepad "Save as" may add `.txt`: the file has no extension.

[commands.md](commands.md) explains the two scripts that use these keys.

## What the lab doesn't allow

- **Least-privilege IAM roles.** Learner Lab can't create roles, so the app and the mode function run as `LabRole`, which may do much more than they need. [infra/iam/](../infra/iam/) has the exact policies each should have in a real account.
- **Encryption all the way to the app.** The browser–AWS leg is HTTPS; API Gateway → Beanstalk stays HTTP. Closing it needs a private VPC link, which needs a load balancer and a certificate for a domain you own, neither available here.
- **CloudFront.** It could give HTTPS and show the waking-up page in place of *any* page of a sleeping portal, but every call is refused (`not authorized to perform: cloudfront:ListDistributions … because no identity-based policy allows`). API Gateway does both jobs here, with one difference: only `/launch` wakes the portal, so share that link.

## When something goes wrong

| Symptom | Likely cause |
| --- | --- |
| Everything fails with `explicit deny`, mentioning `voc-cancel-cred` or a `service control policy` | The lab session ended, or the tab or keys are from an old session. Start the lab, reopen the console from the lab page, and copy the new keys |
| A stack is gone, but a red `awseb-…` stack or a `cloud-dev` environment remains | A delete was cut off by the session's end: see [If a delete was cut off](#if-a-delete-was-cut-off) |
| Connection refused or reset while Beanstalk shows Green | The instance is stuck without the app, usually after a lab session ended. Replace it: see [When a lab session ends](#when-a-lab-session-ends) |
| A redeploy reports success in seconds but the portal stays down | Same cause: replace the instance |
| The Beanstalk address answers "เปิดพอร์ทัลผ่านที่อยู่ HTTPS ของพอร์ทัล" | Expected once the app is locked to its HTTPS address: use that address. A 403 at the HTTPS address too means the secret in API Gateway differs from the app's |
| `Service Unavailable` at the HTTPS address | The app is asleep or still starting: open the launcher link (`…/launch`), or wait a few minutes |
| Stack shows `CREATE_COMPLETE` but the portal never answers | Beanstalk counts its environment as created even if the app crashes: Beanstalk → **Events** and **Logs** |
| Environment "Severe", log shows `connection timeout` to the database | `portal-app-sg` isn't on the instance, or `portal-db-sg` doesn't allow 5432 from it, or Aurora still has the `default` security group |
| `password authentication failed` | `DB_USER` / `DB_PASSWORD` don't match the database user |
| `AccessDenied` from S3 | Instance profile isn't LabInstanceProfile, or `DOCS_BUCKET` is misspelled |
| First deploy fails during `npm run build` | Not enough memory: use t3.medium, and check t3.micro isn't selected too |
| Aurora creation fails mentioning a monitoring role | Enhanced Monitoring is on: turn it off |
| Aurora creation fails: `not authorized to perform rds:CreateDBInstance` … `explicit deny` | Serverless (or a large instance class) chosen: use Provisioned, db.t3.medium |
| Beanstalk creation fails: `Tag key 'Name' is reserved` | Remove the `Name` tag |
| Beanstalk creation fails: `Application Version v1 already exists` | An earlier attempt uploaded it: choose **Existing version**, or use a new label |
| Deploy fails retrieving secrets | A typo in a parameter ARN, or the parameter isn't in us-east-1 |
| Portal shows database errors at the start of a session | Aurora is stopped: start it and wait for Available, or use the launcher link |
| The waking-up page never finishes | Read the function's logs (CloudWatch). A cluster still `stopping` can't start until it has stopped; the page keeps asking, so it continues by itself |
| Delete fails: `Db cluster portal-db is in stopped state` | A stopped cluster can't be deleted: start Aurora, wait for **Available**, delete again. The Lab 2 stack does this by itself |
| Cognito's page: "Incorrect username or password" with a temporary password | The account doesn't exist yet, or a full stop was copied too: the sentence in the email ends with one, which isn't part of the password. Copy and paste; `1` and `l` look alike |
| Cognito's address doesn't load ("server not found"), though the pool and domain exist | It was opened before the new name had spread, and your DNS server remembered that it doesn't exist. This happened on a university network and hadn't cleared after 10 minutes. Wait, try another network, or give the pool a new domain name and wait 2 minutes before opening it |
| After Cognito: "เข้าสู่ระบบไม่สำเร็จ" | Usually the page sat open too long, or was started in another browser. Sign in again from the portal. The reason is in the app's log: `Cognito sign-in refused` |
| After Cognito: "อีเมลนี้ใช้กับพอร์ทัลไม่ได้" | The email's domain isn't in `ALLOWED_EMAIL_DOMAINS`, or the address is already linked to another Cognito user, such as after a pool was recreated while the database stayed |
| A stack fails with "already exists" | Resources from the other lab, or a failed attempt, still use the same names: delete them first |

Where to read logs: Beanstalk → **Logs → Request logs → Full logs**. The app's output is under `var/log/eb-docker/containers/eb-current-app/`.
