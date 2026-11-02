"""Build the whole portal from zero, or delete all of it (infra/full-stack.yaml).

    python scripts/portal_stack.py create you@example.org   # about 12 minutes
    python scripts/portal_stack.py status
    python scripts/portal_stack.py delete                   # asks first; all data is lost

A delete cut off by the end of a lab session can leave Beanstalk's environment
behind, even though the stack itself disappears. `delete` looks for those leftovers
afterwards, and you can run it again at any time to clear them.

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
from botocore.exceptions import ClientError, NoCredentialsError

STACK = "gargantua"
REGION = "us-east-1"
ENVIRONMENT = "cloud-dev"
APPLICATION = "cloud-dev-portal"
TEMPLATE = Path(__file__).resolve().parent.parent / "infra" / "full-stack.yaml"
TAGS = [{"Key": "Project", "Value": "cloud-dev-portal"}, {"Key": "Environment", "Value": "dev"}]
POLL_SECONDS = 15
APP_WAIT_SECONDS = 600
SESSION_ENDED = """AWS refused the request: your lab session has ended, or these keys are from an old one.
Anything already started may have stopped partway.
Start the lab, copy the new keys into ~/.aws/credentials, and run this command again."""


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


def session_ended(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")
    return code in ("ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId") or (
        code.startswith(("AccessDenied", "Unauthorized")) and "explicit deny" in str(error))


def leftovers(cfn, eb) -> list[str]:
    """What an interrupted delete can leave behind. Names match Lab 1's hand-built
    environment too, so nothing here proves these came from the stack."""
    found = []
    if eb.describe_environments(EnvironmentNames=[ENVIRONMENT], IncludeDeleted=False)["Environments"]:
        found.append(f"Beanstalk environment {ENVIRONMENT}")
    if eb.describe_applications(ApplicationNames=[APPLICATION])["Applications"]:
        found.append(f"Beanstalk application {APPLICATION}")
    failed = cfn.list_stacks(StackStatusFilter=["DELETE_FAILED"])["StackSummaries"]
    found += [f"failed stack {s['StackName']}" for s in failed if s["StackName"].startswith("awseb-e-")]
    return found


def remove_leftovers(cfn, eb) -> None:
    if eb.describe_environments(EnvironmentNames=[ENVIRONMENT], IncludeDeleted=False)["Environments"]:
        eb.terminate_environment(EnvironmentName=ENVIRONMENT)
    while eb.describe_environments(EnvironmentNames=[ENVIRONMENT], IncludeDeleted=False)["Environments"]:
        time.sleep(POLL_SECONDS)
    if eb.describe_applications(ApplicationNames=[APPLICATION])["Applications"]:
        eb.delete_application(ApplicationName=APPLICATION, TerminateEnvByForce=True)
    for stack in cfn.list_stacks(StackStatusFilter=["DELETE_FAILED"])["StackSummaries"]:
        if stack["StackName"].startswith("awseb-e-"):
            cfn.delete_stack(StackName=stack["StackName"])


def clear_leftovers(cfn, eb, confirmed: bool) -> int:
    found = leftovers(cfn, eb)
    if not found:
        return 0
    print("Found, with names this portal uses:\n  " + "\n  ".join(found))
    print("Either a delete was interrupted, or you built these by hand in Lab 1.")
    if not confirmed and input("Remove them? Type remove to confirm: ").strip() != "remove":
        print("Left in place.")
        return 1
    remove_leftovers(cfn, eb)
    remaining = leftovers(cfn, eb)
    print("Removed." if not remaining else "Still removing: " + ", ".join(remaining) + ". Run this again shortly.")
    return 0


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
    print("Password: Cognito has emailed a temporary one to that address")
    return 0


def delete(cfn, eb, confirmed: bool) -> int:
    if not stack_info(cfn):
        print(f"There is no stack {STACK}.")
        # Not covered by --yes: with no stack, these could be a hand-built Lab 1.
        return clear_leftovers(cfn, eb, confirmed=False)
    if not confirmed and input(f"Delete {STACK} and ALL portal data? Type {STACK} to confirm: ").strip() != STACK:
        print("Nothing deleted.")
        return 1
    cfn.delete_stack(StackName=STACK)
    if wait_for_stack(cfn):
        print_failures(cfn)
        print("The delete failed; fix the reason above and run this again.")
        return 1
    print("The stack is gone.")
    return clear_leftovers(cfn, eb, confirmed=True)


def status(cfn, eb) -> int:
    info = stack_info(cfn)
    if not info:
        print(f"There is no stack {STACK}.")
        for item in leftovers(cfn, eb):
            print(f"Still there: {item}. Run delete to remove it.")
        return 0
    print(info["StackStatus"])
    found = outputs(info)
    if "PortalUrl" in found:
        print(f"{found['PortalUrl']} {'answers' if answers(found['PortalUrl']) else 'does not answer'}")
    return 0


def main(argv: list[str], cfn=None, eb=None) -> int:
    action, rest = (argv[0], argv[1:]) if argv else ("", [])
    if not (action == "create" and len(rest) == 1 and "@" in rest[0]
            or action == "status" and not rest
            or action == "delete" and rest in ([], ["--yes"])):
        print(__doc__)
        return 2
    cfn = cfn or boto3.client("cloudformation", region_name=REGION)
    eb = eb or boto3.client("elasticbeanstalk", region_name=REGION)
    try:
        if action == "create":
            return create(cfn, rest[0])
        if action == "delete":
            return delete(cfn, eb, rest == ["--yes"])
        return status(cfn, eb)
    except NoCredentialsError:
        print(SESSION_ENDED)
        return 1
    except ClientError as error:
        if session_ended(error):
            print(SESSION_ENDED)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
