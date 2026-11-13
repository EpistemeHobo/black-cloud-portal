"""Delete everything Lab 1 (docs/lab-1-by-hand.md) builds by hand, in the order of its
Clean up section.

    python scripts/lab1_cleanup.py          # lists what it finds; deletes nothing
    python scripts/lab1_cleanup.py --yes    # deletes it: ALL portal data is lost

It finds the user pool and the docs bucket from the Beanstalk environment's settings
(COGNITO_USER_POOL_ID, DOCS_BUCKET), because Lab 1's console names the pool itself
and the bucket name is yours. If the environment is already gone, name them:
--pool us-east-1_AbC123 --bucket my-bucket.

Not deleted: Lab 2's stack (use scripts/portal_stack.py), Beanstalk's own bucket
elasticbeanstalk-us-east-1-<account id>, and LabRole. Takes about 20 minutes, mostly
waiting for Beanstalk and Aurora; start it with at least 30 minutes left in the session.

Uses the AWS credentials from the Learner Lab page in ~/.aws/credentials.
"""
import sys
import time

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION = "us-east-1"
ENVIRONMENT = "cloud-dev"
APPLICATION = "cloud-dev-portal"
API_NAME = "cloud-dev-portal-wake"
RULES = ["cloud-dev-portal-tick", "cloud-dev-portal-nightly-stop"]
FUNCTION = "cloud-dev-portal-mode"
CLUSTER = "portal-db"
APP_SG, DB_SG = "portal-app-sg", "portal-db-sg"
PARAM_PATH = "/cloud-dev-portal/"
POLL = 15


def say(text: str) -> None:
    print(f"{time.strftime('%H:%M')}  {text}", flush=True)


def missing(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")
    return "NotFound" in code or code in ("ResourceNotFoundException", "NoSuchBucket")


class Lab1:
    def __init__(self, pool: str | None, bucket: str | None):
        c = lambda name: boto3.client(name, region_name=REGION)  # noqa: E731
        self.eb, self.idp, self.apigw = c("elasticbeanstalk"), c("cognito-idp"), c("apigatewayv2")
        self.events, self.lam, self.rds = c("events"), c("lambda"), c("rds")
        self.ec2, self.s3, self.ssm = c("ec2"), c("s3"), c("ssm")
        settings = self.env_settings()
        self.pool = pool or settings.get("COGNITO_USER_POOL_ID")
        self.bucket = bucket or settings.get("DOCS_BUCKET")

    # ---------- finding ----------
    def env_settings(self) -> dict:
        try:
            options = self.eb.describe_configuration_settings(
                ApplicationName=APPLICATION, EnvironmentName=ENVIRONMENT)["ConfigurationSettings"][0]["OptionSettings"]
        except ClientError:
            return {}
        return {o["OptionName"]: o.get("Value") for o in options
                if o["Namespace"] == "aws:elasticbeanstalk:application:environment"}

    def env_exists(self) -> bool:
        return bool(self.eb.describe_environments(EnvironmentNames=[ENVIRONMENT], IncludeDeleted=False)["Environments"])

    def app_exists(self) -> bool:
        return bool(self.eb.describe_applications(ApplicationNames=[APPLICATION])["Applications"])

    def api_ids(self) -> list[str]:
        return [a["ApiId"] for a in self.apigw.get_apis()["Items"] if a["Name"] == API_NAME]

    def rules(self) -> list[str]:
        return [r for r in RULES if self.events.list_rules(NamePrefix=r)["Rules"]]

    def function_exists(self) -> bool:
        try:
            self.lam.get_function(FunctionName=FUNCTION)
            return True
        except ClientError as error:
            if missing(error):
                return False
            raise

    def cluster(self) -> dict | None:
        try:
            return self.rds.describe_db_clusters(DBClusterIdentifier=CLUSTER)["DBClusters"][0]
        except ClientError as error:
            if missing(error):
                return None
            raise

    def groups(self) -> dict[str, str]:
        found = self.ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [APP_SG, DB_SG]}])
        return {g["GroupName"]: g["GroupId"] for g in found["SecurityGroups"]}

    def pool_exists(self) -> bool:
        if not self.pool:
            return False
        try:
            self.idp.describe_user_pool(UserPoolId=self.pool)
            return True
        except ClientError as error:
            if missing(error):
                return False
            raise

    def bucket_exists(self) -> bool:
        if not self.bucket:
            return False
        try:
            self.s3.head_bucket(Bucket=self.bucket)
            return True
        except ClientError:
            return False

    def params(self) -> list[str]:
        names, pages = [], self.ssm.get_paginator("get_parameters_by_path")
        for page in pages.paginate(Path=PARAM_PATH.rstrip("/"), Recursive=True):
            names += [p["Name"] for p in page["Parameters"]]
        return names

    def inventory(self) -> list[str]:
        found = []
        if self.pool_exists():
            found.append(f"Cognito user pool {self.pool}, with its domain and users")
        if self.env_exists():
            found.append(f"Beanstalk environment {ENVIRONMENT}")
        if self.app_exists():
            found.append(f"Beanstalk application {APPLICATION}, with its versions")
        found += [f"API Gateway {API_NAME} ({i})" for i in self.api_ids()]
        found += [f"EventBridge rule {r}" for r in self.rules()]
        if self.function_exists():
            found.append(f"Lambda function {FUNCTION}")
        cluster = self.cluster()
        if cluster:
            members = ", ".join(m["DBInstanceIdentifier"] for m in cluster["DBClusterMembers"])
            found.append(f"Aurora cluster {CLUSTER} ({cluster['Status']}), instances: {members or 'none'}")
        found += [f"Security group {name} ({gid})" for name, gid in self.groups().items()]
        if self.bucket_exists():
            found.append(f"S3 bucket {self.bucket}, with every file and version in it")
        elif not self.bucket:
            found.append("S3 bucket: unknown (the environment is gone); pass --bucket NAME to delete it")
        found += [f"SSM parameter {p}" for p in self.params()]
        return found

    # ---------- deleting ----------
    def delete_pool(self) -> None:
        if not self.pool_exists():
            return
        domain = self.idp.describe_user_pool(UserPoolId=self.pool)["UserPool"].get("Domain")
        if domain:  # a pool can't be deleted while it has a domain
            self.idp.delete_user_pool_domain(Domain=domain, UserPoolId=self.pool)
        self.idp.delete_user_pool(UserPoolId=self.pool)
        say(f"deleted user pool {self.pool}")

    def delete_timers_and_function(self) -> None:
        # First, so the function can't start or stop anything while the rest goes.
        for rule in self.rules():
            targets = [t["Id"] for t in self.events.list_targets_by_rule(Rule=rule)["Targets"]]
            if targets:
                self.events.remove_targets(Rule=rule, Ids=targets)
            self.events.delete_rule(Name=rule)
            say(f"deleted rule {rule}")
        if self.function_exists():
            self.lam.delete_function(FunctionName=FUNCTION)
            say(f"deleted function {FUNCTION}")
        for api in self.api_ids():
            self.apigw.delete_api(ApiId=api)
            say(f"deleted API {API_NAME}")

    def delete_beanstalk(self) -> None:
        if self.env_exists():
            self.eb.terminate_environment(EnvironmentName=ENVIRONMENT)
            say(f"terminating environment {ENVIRONMENT} (about 5 to 10 minutes)")
            while self.env_exists():
                time.sleep(POLL)
            say("environment terminated")
        if self.app_exists():
            self.eb.delete_application(ApplicationName=APPLICATION, TerminateEnvByForce=True)
            say(f"deleted application {APPLICATION}")

    def delete_aurora(self) -> None:
        cluster = self.cluster()
        if not cluster:
            return
        if cluster.get("DeletionProtection"):
            self.rds.modify_db_cluster(DBClusterIdentifier=CLUSTER, DeletionProtection=False, ApplyImmediately=True)
        if cluster["Status"] in ("stopped", "stopping"):
            # A stopped cluster can't be deleted.
            while self.cluster()["Status"] == "stopping":
                time.sleep(POLL)
            self.rds.start_db_cluster(DBClusterIdentifier=CLUSTER)
            say("starting Aurora so it can be deleted (about 5 minutes)")
        while self.cluster()["Status"] != "available":
            time.sleep(POLL)
        for member in cluster["DBClusterMembers"]:
            self.rds.delete_db_instance(DBInstanceIdentifier=member["DBInstanceIdentifier"])
            say(f"deleting instance {member['DBInstanceIdentifier']}")
        for member in cluster["DBClusterMembers"]:
            self.rds.get_waiter("db_instance_deleted").wait(
                DBInstanceIdentifier=member["DBInstanceIdentifier"], WaiterConfig={"Delay": POLL, "MaxAttempts": 120})
        self.rds.delete_db_cluster(DBClusterIdentifier=CLUSTER, SkipFinalSnapshot=True)
        say(f"deleting cluster {CLUSTER}, no final snapshot")
        while self.cluster():
            time.sleep(POLL)
        say("Aurora deleted")

    def delete_groups(self) -> None:
        groups = self.groups()
        if DB_SG in groups:  # its rule points at the app's group, which can't go while referenced
            rules = self.ec2.describe_security_groups(GroupIds=[groups[DB_SG]])["SecurityGroups"][0]["IpPermissions"]
            if rules:
                self.ec2.revoke_security_group_ingress(GroupId=groups[DB_SG], IpPermissions=rules)
        for name in (APP_SG, DB_SG):
            if name not in groups:
                continue
            for _ in range(40):  # network interfaces of deleted servers take a few minutes to go
                try:
                    self.ec2.delete_security_group(GroupId=groups[name])
                    say(f"deleted security group {name}")
                    break
                except ClientError as error:
                    if error.response["Error"]["Code"] != "DependencyViolation":
                        raise
                    time.sleep(POLL)
            else:
                say(f"security group {name} is still in use; run this again in a few minutes")

    def delete_bucket(self) -> None:
        if not self.bucket_exists():
            return
        pages = self.s3.get_paginator("list_object_versions")
        for page in pages.paginate(Bucket=self.bucket):
            keys = [{"Key": v["Key"], "VersionId": v["VersionId"]}
                    for v in page.get("Versions", []) + page.get("DeleteMarkers", [])]
            if keys:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": keys, "Quiet": True})
        self.s3.delete_bucket(Bucket=self.bucket)
        say(f"deleted bucket {self.bucket}")

    def delete_params(self) -> None:
        names = self.params()
        for start in range(0, len(names), 10):
            self.ssm.delete_parameters(Names=names[start:start + 10])
        if names:
            say(f"deleted {len(names)} SSM parameters under {PARAM_PATH}")

    def delete_all(self) -> None:
        self.delete_timers_and_function()
        self.delete_pool()
        self.delete_beanstalk()
        self.delete_aurora()
        self.delete_groups()
        self.delete_bucket()
        self.delete_params()


def option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def main(args: list[str]) -> int:
    known = {"--yes", "--pool", "--bucket"}
    if any(a.startswith("--") and a not in known for a in args):
        print(__doc__)
        return 2
    try:
        lab = Lab1(option(args, "--pool"), option(args, "--bucket"))
        found = lab.inventory()
        if not found:
            print("Nothing from Lab 1 is left.")
            return 0
        print("Found:\n  " + "\n  ".join(found))
        if "--yes" not in args:
            print("\nNothing deleted. Run again with --yes to delete all of it: the portal's data can't be recovered.")
            return 0
        lab.delete_all()
        left = [f for f in lab.inventory() if not f.startswith("S3 bucket: unknown")]
        print("\nAll gone." if not left else "\nStill there:\n  " + "\n  ".join(left))
        return 0 if not left else 1
    except NoCredentialsError:
        print("No AWS credentials: copy them from the Learner Lab page into ~/.aws/credentials.")
        return 1
    except ClientError as error:
        if error.response.get("Error", {}).get("Code", "") in ("ExpiredToken", "ExpiredTokenException"):
            print("Your lab session has ended or these keys are old: copy the new ones and run this again.")
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
