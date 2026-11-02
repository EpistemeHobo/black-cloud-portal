# IAM policies: least privilege, written down

AWS Academy Learner Lab can't create IAM roles, so in the lab the app and the
mode function run as `LabRole` / `LabInstanceProfile`, which may do far more than
they need. These files are what each part should be allowed instead, for a real
account (replace `ACCOUNT_ID`, `BUCKET_NAME`, `ENVIRONMENT_NAME`).

| File | Attach to | Allows only |
| --- | --- | --- |
| `portal-app-instance-policy.json` | The Beanstalk instance's role, with the AWS managed policies `AWSElasticBeanstalkWebTier` (logs, deployment bucket) and `AmazonSSMManagedInstanceCore` (Session Manager) | Its own guide files in S3; reading its three secrets; decrypting them through SSM |
| `portal-mode-lambda-policy.json` | The mode function's role | Starting and stopping the `portal-db` cluster; resizing this environment's instance group; reading and writing its two state parameters; its own logs |
| `docs-bucket-policy.json` | The docs bucket (bucket policy; applied in the lab too) | Nothing over plain HTTP |

Each `Sid` names what the statement grants. The few `"Resource": "*"` entries are
read-only describe calls, or `UpdateAutoScalingGroup` narrowed by the
environment's tag, because those actions can't be limited by resource name.

Cognito sign-in needs no IAM permission for the app: it only uses the user pool's
public sign-in and key addresses. Whoever creates the pool needs `cognito-idp`
permissions, but the running app doesn't.

`python -m app.app_db_user` additionally needs `ssm:PutParameter` on
`/cloud-dev-portal/db-password` once, when it stores the new password; give it
to whoever runs that step, not to the app.
