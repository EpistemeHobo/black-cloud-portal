# 6. Active and hibernate modes on AWS

*Date: 2026-11-01 · Status: Accepted*

## Context

The class project runs on AWS Academy Learner Lab with a fixed budget. Aurora (provisioned `db.t3.medium`, since Learner Lab refuses Aurora Serverless) and the Beanstalk instance cost about $2.50 a day while running, yet the portal is used only on some days: heavily on presentation days, briefly while developing.

## Decision

Two modes, kept in SSM Parameter Store and switched with one Lambda function (`cloud-dev-portal-mode`, from a saved console test event or `scripts/portal_mode.py`):

1. **Active**: Aurora and the instance stay on. Every 15 minutes the function turns back on anything AWS stopped.
2. **Hibernate**: every 15 minutes the function asks the app how long it has been idle (`/api/health` reports `idle_seconds`, not counting itself) and, after 30 minutes, sets the Beanstalk group to 0 instances and stops Aurora.
3. **Wake on visit, through a launcher link**: the API Gateway address, answered by the same function. When the portal is awake it redirects there; when it sleeps it returns a waking-up page, which calls `/_wake/start` every 10 seconds until Aurora is available and the app answers, then forwards to the portal.
4. **The app waits for the database** on start (`docker-entrypoint.sh` retries migrations for 15 minutes), so the instance and Aurora start together.
5. Everything is one CloudFormation stack using LabRole, so it can be removed in one step. The guide also builds it by hand, for teaching.

## Options considered

- **Aurora Serverless v2 scaling to 0**: wakes in seconds, but Learner Lab denies it.
- **CloudFront with an origin group** (first design): shows the waking-up page at the portal's own address when the app doesn't answer, and adds HTTPS. Learner Lab denies every CloudFront action, so it was dropped.
- **Scheduled start and stop only**: simpler, but no wake on visit; the portal is either on all day or off when needed.
- **Stopping the EC2 instance instead of 0 instances**: faster to wake (the built image stays on its disk), but Beanstalk's group replaces a stopped instance as unhealthy.

## Consequences

- Waking takes 5 to 10 minutes, mostly Aurora starting; the instance rebuilds the image meanwhile. Building the image into ECR would shorten the instance's part.
- While asleep, Beanstalk reports the environment as unhealthy, and deploys fail until it is woken.
- The link to share is the launcher, not the Beanstalk address: the Beanstalk address doesn't answer while the portal sleeps.
- Learner Lab appears to block `LabRole` while no session is open, so the idle check and the midnight rule may not run then, and an instance replaced during that time is left without the app. Switch to hibernate before a session ends (guide: "When a lab session ends").
- Anyone with the launcher link can wake the portal; API Gateway throttling limits the calls, and it sleeps again after 30 idle minutes.
- The portal itself stays on plain HTTP (only the launcher has HTTPS).
