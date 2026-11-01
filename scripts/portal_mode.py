"""Switch the portal on AWS between active and hibernate mode, wake it, or see its state.

    python scripts/portal_mode.py active      # presentation day: everything on, no sleeping
    python scripts/portal_mode.py hibernate   # development days: sleeps when idle, wakes on a visit
    python scripts/portal_mode.py wake        # wake it now, stay in hibernate
    python scripts/portal_mode.py status

Uses the AWS credentials from the Learner Lab page (AWS Details → AWS CLI) in
~/.aws/credentials. Calls the cloud-dev-portal-mode function (infra/sleep-wake.yaml).
"""
import json
import sys

import boto3

FUNCTION = "cloud-dev-portal-mode"
EVENTS = {
    "active": {"mode": "active"},
    "hibernate": {"mode": "hibernate"},
    "wake": {"action": "wake"},
    "status": {"action": "status"},
}


def main(argv: list[str]) -> None:
    if len(argv) != 1 or argv[0] not in EVENTS:
        raise SystemExit(__doc__)
    client = boto3.client("lambda", region_name="us-east-1")
    response = client.invoke(FunctionName=FUNCTION, Payload=json.dumps(EVENTS[argv[0]]).encode())
    result = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise SystemExit(f"The function failed: {result.get('errorMessage', result)}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
