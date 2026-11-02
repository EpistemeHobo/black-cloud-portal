# 7. Security hardening on AWS

*Date: 2026-11-01 · Status: Accepted*

## Context

The first AWS deployment (decisions 0005, 0006) worked, but took shortcuts: the app signed in to Aurora as the master user, passwords sat in plain text in the Beanstalk configuration, choosing a key pair opened SSH to the internet, the seed admin's password stayed configured after use, and the portal was plain HTTP. The project is also a lesson in least privilege and in not leaving authority lying around, so it should practise them.

## Decision

1. **No SSH.** No key pair on the Beanstalk environment; shells go through Session Manager.
2. **The app's own database user.** `python -m app.app_db_user` creates `portal_app` and a `portal` database only it may connect to, copies the data, and stores the password in SSM. The master password is no longer configured anywhere.
3. **Secrets in SSM Parameter Store** as SecureStrings (`db-password`, `jwt-secret-key`, `origin-verify-secret`), linked to the Beanstalk properties by ARN, so the configuration shows no secret.
4. **No seed admin password** after the first start. With Cognito (decision 0008) there's none at all.
5. **S3 refuses plain HTTP** (bucket policy).
6. **HTTPS through API Gateway.** The API passes the portal's pages to Beanstalk and overwrites an `X-Origin-Verify` header with a shared secret; the app refuses requests without it (except `/api/health`), so the HTTPS address is the only way in. Cookies are `Secure`. The app's trailing-slash redirects are made relative, so they stay on the HTTPS address.
7. **The waking-up page's public calls** return only `database_ready`, `app_ready` and `ready`; the launcher moves to `/launch`. Those routes are throttled tightly (they can start servers); the portal's pages get room for ~20 files per page load.
8. **Least-privilege IAM policies are written down** in `infra/iam/`, since Learner Lab can't create roles.

## Options considered

- **Secrets in Secrets Manager**: rotation built in, but costs per secret; SecureStrings are free and enough here.
- **A load balancer with HTTPS**: needs a certificate for a domain we own, which Learner Lab can't register, and costs about $0.55 a day.
- **Restricting port 80 to API Gateway's addresses**: API Gateway has no fixed addresses; the secret header does the same job.

## Consequences

- The app and the mode function still run as `LabRole`, which allows far more than they need; only a real account fixes that.
- API Gateway → Beanstalk stays HTTP (no VPC link without a load balancer).
- Every page goes through API Gateway: $1 per million requests, and its 30-second and 10 MB limits apply.
- The old tables in the `postgres` database remain until dropped by hand.
