# 6. Active and hibernate modes on AWS

*Date: 2026-11-01 · Status: Accepted*

## Context

The class project runs on AWS Academy Learner Lab with a fixed budget. Aurora (provisioned `db.t3.medium`, since Learner Lab refuses Aurora Serverless) and the Beanstalk instance cost about $2.50 a day while running, yet the portal is used only on some days: heavily on presentation days, briefly while developing.

## Decision

Two modes, kept in SSM Parameter Store and switched with one Lambda function (`cloud-dev-portal-mode`, from a saved console test event or `scripts/portal_mode.py`):

1. **Active**: Aurora and the instance stay on. Every 15 minutes the function turns back on anything AWS stopped.
2. **Hibernate**: every 15 minutes the function asks the app how long it has been idle (`/api/health` reports `idle_seconds`, not counting itself) and, after 30 minutes, sets the Beanstalk group to 0 instances and stops Aurora.
3. **Wake on visit**: CloudFront fronts the app. When the app doesn't answer (3-second connection timeout, or a 5xx), an origin group fails over to API Gateway, which returns a waking-up page from the same function. The page calls `/_wake/start` every 10 seconds until Aurora is available and the app answers, then reloads.
4. **The app waits for the database** on start (`docker-entrypoint.sh` retries migrations for 15 minutes), so the instance and Aurora start together.
5. **`/api/*` bypasses the origin group**: CloudFront allows only GET/HEAD/OPTIONS on a behavior with an origin group.
6. Everything is one CloudFormation stack using LabRole, so it can be removed in one step.

## Options considered

- **Aurora Serverless v2 scaling to 0**: wakes in seconds, but Learner Lab denies it.
- **Scheduled start and stop only**: simpler, but no wake on visit; the portal is either on all day or off when needed.
- **Stopping the EC2 instance instead of 0 instances**: faster to wake (the built image stays on its disk), but Beanstalk's group replaces a stopped instance as unhealthy.

## Consequences

- Waking takes 5 to 10 minutes, mostly Aurora starting; the instance rebuilds the image meanwhile. Building the image into ECR would shorten the instance's part.
- While asleep, Beanstalk reports the environment as unhealthy, and deploys fail until it is woken.
- Anyone who opens the site can wake it; API Gateway throttling limits the calls, and it sleeps again after 30 idle minutes.
- The public address becomes the CloudFront one (HTTPS), which Cognito will need anyway.
