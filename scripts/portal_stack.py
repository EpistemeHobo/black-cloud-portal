"""Build the whole portal from zero, or delete all of it (infra/full-stack.yaml).

    python scripts/portal_stack.py create you@example.org   # about 12 minutes
    python scripts/portal_stack.py status
    python scripts/portal_stack.py delete                   # asks first; all data is lost

The same as CloudFormation's Create stack and Delete buttons, with the waiting done
for you. `create` isn't finished at CREATE_COMPLETE: that doesn't prove the app
started, so it also waits until the portal's HTTPS address answers.

Uses the AWS credentials from the Learner Lab page (AWS Details, AWS CLI) in
~/.aws/credentials; they change every session.
"""
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

STACK = "gargantua"
REGION = "us-east-1"
TEMPLATE = Path(__file__).resolve().parent.parent / "infra" / "full-stack.yaml"
TAGS = [{"Key": "Project", "Value": "cloud-dev-portal"}, {"Key": "Environment", "Value": "dev"}]
POLL_SECONDS = 15
APP_WAIT_SECONDS = 600


def stack_info(cfn) -> dict | None:
    try:
        return cfn.describe_stacks(StackName=STACK)["Stacks"][0]
    except ClientError as error:
        if "does not exist" in str(error):
            return None
        raise


def wait_for_stack(cfn) -> dict | None:
    """Wait until the stack stops changing, printing each new status. None once it's gone."""
    last = None
    while True:
        info = stack_info(cfn)
        status = info["StackStatus"] if info else None
        if status != last:
            print(f"{time.strftime('%H:%M')}  {status or 'gone'}", flush=True)
            last = status
        if not status or not status.endswith("_IN_PROGRESS"):
            return info
        time.sleep(POLL_SECONDS)


def print_failures(cfn) -> None:
    for event in cfn.describe_stack_events(StackName=STACK)["StackEvents"]:
        if "FAILED" in event["ResourceStatus"]:
            print(f"  {event['LogicalResourceId']}: {event.get('ResourceStatusReason', '')}")


def outputs(info: dict) -> dict:
    return {o["OutputKey"]: o["OutputValue"] for o in info.get("Outputs", [])}


def answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def wait_for_app(url: str) -> bool:
    deadline = time.monotonic() + APP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if answers(url):
            return True
        time.sleep(POLL_SECONDS)
    return False


def create(cfn, email: str) -> int:
    if stack_info(cfn):
        print(f"Stack {STACK} already exists: delete it first.")
        return 1
    cfn.create_stack(
        StackName=STACK, TemplateBody=TEMPLATE.read_text(encoding="utf-8"), Tags=TAGS,
        Parameters=[{"ParameterKey": "AdminEmail", "ParameterValue": email}],
        OnFailure="DELETE",  # a failed attempt leaves nothing behind
    )
    info = wait_for_stack(cfn)
    if not info or info["StackStatus"] != "CREATE_COMPLETE":
        print("The stack failed; CloudFormation's Events tab (deleted stacks filter) has the reason.")
        return 1
    found = outputs(info)
    print("Stack built. Waiting for the portal to answer...", flush=True)
    if not wait_for_app(found["PortalUrl"]):
        print(f"The stack is complete, but {found['PortalUrl']} doesn't answer: the app failed to start.")
        print("See Beanstalk, environment cloud-dev: Events and Logs.")
        return 1
    print(f"\nPortal:   {found['PortalUrl']}\nLauncher: {found['LauncherUrl']}\nAdmin:    {found['AdminEmail']}")
    print(f"Password: Secrets Manager, Retrieve secret value of\n          {found['AdminPasswordSecret']}")
    return 0


def delete(cfn, confirmed: bool) -> int:
    if not stack_info(cfn):
        print(f"There is no stack {STACK}: nothing to delete.")
        return 0
    if not confirmed and input(f"Delete {STACK} and ALL portal data? Type {STACK} to confirm: ").strip() != STACK:
        print("Nothing deleted.")
        return 1
    cfn.delete_stack(StackName=STACK)
    if wait_for_stack(cfn):
        print_failures(cfn)
        print("The delete failed; fix the reason above and run this again.")
        return 1
    print("Everything from the stack is gone.")
    return 0


def status(cfn) -> int:
    info = stack_info(cfn)
    if not info:
        print(f"There is no stack {STACK}.")
        return 0
    print(info["StackStatus"])
    found = outputs(info)
    if "PortalUrl" in found:
        print(f"{found['PortalUrl']} {'answers' if answers(found['PortalUrl']) else 'does not answer'}")
    return 0


def main(argv: list[str], cfn=None) -> int:
    action, rest = (argv[0], argv[1:]) if argv else ("", [])
    if not (action == "create" and len(rest) == 1 and "@" in rest[0]
            or action == "status" and not rest
            or action == "delete" and rest in ([], ["--yes"])):
        print(__doc__)
        return 2
    cfn = cfn or boto3.client("cloudformation", region_name=REGION)
    if action == "create":
        return create(cfn, rest[0])
    if action == "delete":
        return delete(cfn, rest == ["--yes"])
    return status(cfn)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
