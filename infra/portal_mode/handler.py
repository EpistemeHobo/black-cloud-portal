"""Active and hibernate modes for the portal on AWS (docs/aws-learner-lab.md).

- active: Aurora and the Beanstalk instance stay on, for presentation days.
- hibernate: both sleep after IDLE_MINUTES without visitors and wake when someone
  opens the site, for development days.

One Lambda function does all of it, depending on what calls it:

- You (Lambda console test event or scripts/portal_mode.py):
  {"mode": "active"}, {"mode": "hibernate"}, {"action": "wake"}, {"action": "status"}
- EventBridge, every 15 minutes: {"action": "tick"}, which sleeps an idle portal
- API Gateway: its address is the portal's launcher link. Opening it forwards to
  the portal when it's awake, or shows the "waking up" page, which wakes it
  through /_wake/start and forwards when it's ready. (Learner Lab doesn't allow
  CloudFront, which could have shown that page at the portal's own address.)

The mode and the time of the last wake are kept in SSM Parameter Store.
"""
import json
import os
import time
import urllib.request
from pathlib import Path

import boto3

CLUSTER = os.environ.get("DB_CLUSTER_ID", "portal-db")
ENVIRONMENT = os.environ.get("EB_ENVIRONMENT", "")
PARAM_PREFIX = os.environ.get("PARAM_PREFIX", "/cloud-dev-portal")
IDLE_MINUTES = int(os.environ.get("IDLE_MINUTES", "30"))

ACTIVE, HIBERNATE = "active", "hibernate"
WAKE_PAGE = (Path(__file__).parent / "wake.html").read_text(encoding="utf-8")

rds = boto3.client("rds")
autoscaling = boto3.client("autoscaling")
beanstalk = boto3.client("elasticbeanstalk")
ssm = boto3.client("ssm")


# ---------- What AWS says right now ----------

def get_param(name: str, default: str) -> str:
    try:
        return ssm.get_parameter(Name=f"{PARAM_PREFIX}/{name}")["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return default


def put_param(name: str, value: str) -> None:
    ssm.put_parameter(Name=f"{PARAM_PREFIX}/{name}", Value=value, Type="String", Overwrite=True)


def db_status() -> str:
    """available, stopped, starting, stopping, ..."""
    return rds.describe_db_clusters(DBClusterIdentifier=CLUSTER)["DBClusters"][0]["Status"]


def app_group() -> str:
    resources = beanstalk.describe_environment_resources(EnvironmentName=ENVIRONMENT)["EnvironmentResources"]
    return resources["AutoScalingGroups"][0]["Name"]


def app_instances(group: str) -> int:
    """How many instances the Beanstalk group is set to run (0 while asleep)."""
    return autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[group])["AutoScalingGroups"][0]["DesiredCapacity"]


def app_url() -> str:
    env = beanstalk.describe_environments(EnvironmentNames=[ENVIRONMENT])["Environments"][0]
    return f"http://{env['CNAME']}"


def app_idle_seconds() -> int | None:
    """Seconds since someone last used the portal; None when it doesn't answer."""
    try:
        with urllib.request.urlopen(f"{app_url()}/api/health", timeout=3) as response:
            return int(json.load(response).get("idle_seconds", 0))
    except Exception:
        return None


def status() -> dict:
    group = app_group()
    idle = app_idle_seconds()
    db = db_status()
    return {
        "mode": get_param("mode", HIBERNATE),
        "app_url": app_url(),
        "database": db,
        "app_instances": app_instances(group),
        "app_answers": idle is not None,
        "idle_minutes": None if idle is None else idle // 60,
        "ready": db == "available" and idle is not None,
    }


# ---------- Waking and sleeping ----------

def wake() -> dict:
    """Start whatever is asleep. The app waits for the database by itself
    (docker-entrypoint.sh), so both start together."""
    put_param("woken-at", str(int(time.time())))
    if db_status() == "stopped":
        rds.start_db_cluster(DBClusterIdentifier=CLUSTER)
    group = app_group()
    if app_instances(group) == 0:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=group, MinSize=1, MaxSize=1, DesiredCapacity=1)
    return status()


def sleep() -> dict:
    group = app_group()
    if app_instances(group) > 0:
        autoscaling.update_auto_scaling_group(AutoScalingGroupName=group, MinSize=0, MaxSize=0, DesiredCapacity=0)
    # A cluster that is still starting can't be stopped yet; the next tick tries again.
    if db_status() == "available":
        rds.stop_db_cluster(DBClusterIdentifier=CLUSTER)
    return status()


def should_sleep(mode: str, woken_at: int, idle_seconds: int | None, now: float) -> bool:
    """The tick's decision. Never in active mode, nor while a wake is in progress
    (the app doesn't answer for several minutes after one). After that, sleep when
    the app has been idle long enough, or doesn't answer at all (asleep already,
    or a wake that failed: don't leave Aurora running for nothing)."""
    if mode != HIBERNATE:
        return False
    if now - woken_at < IDLE_MINUTES * 60:
        return False
    return idle_seconds is None or idle_seconds >= IDLE_MINUTES * 60


def tick() -> dict:
    mode = get_param("mode", HIBERNATE)
    if mode == ACTIVE:
        # AWS restarts a stopped cluster after 7 days and may replace instances;
        # in active mode, just make sure everything is on.
        return wake()
    if should_sleep(mode, int(get_param("woken-at", "0")), app_idle_seconds(), time.time()):
        return sleep()
    return status()


def set_mode(mode: str) -> dict:
    if mode not in (ACTIVE, HIBERNATE):
        raise ValueError(f"Unknown mode {mode!r}: use {ACTIVE!r} or {HIBERNATE!r}.")
    put_param("mode", mode)
    return wake() if mode == ACTIVE else sleep()


# ---------- Entry point ----------

def http_response(code: int, body: str, content_type: str, **headers: str) -> dict:
    return {"statusCode": code, "body": body,
            "headers": {"Content-Type": content_type, "Cache-Control": "no-store", **headers}}


def handle_http(event: dict) -> dict:
    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "/")
    if path == "/_wake/start" and method == "POST":
        return http_response(200, json.dumps(wake()), "application/json")
    if path == "/_wake/status":
        return http_response(200, json.dumps(status()), "application/json")
    # The launcher link: straight on to the portal when it's up, otherwise the
    # waking-up page (503, so nothing treats it as the real one).
    if app_idle_seconds() is not None and db_status() == "available":
        return http_response(302, "", "text/plain", Location=app_url())
    return http_response(503, WAKE_PAGE, "text/html; charset=utf-8")


def lambda_handler(event: dict, _context) -> dict:
    if "requestContext" in event:
        return handle_http(event)
    if "mode" in event:
        return set_mode(event["mode"])
    action = event.get("action", "status")
    if action == "wake":
        return wake()
    if action == "tick":
        return tick()
    if action == "status":
        return status()
    raise ValueError(f"Unknown action {action!r}.")
