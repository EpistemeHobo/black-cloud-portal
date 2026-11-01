"""The mode function's decisions, with the AWS clients replaced by fakes.

Run from the repository root: python -m pytest infra
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "portal_mode"))
import handler  # noqa: E402

GROUP = "awseb-cloud-dev-portal-asg"
NOW = 1_800_000_000


class FakeAws:
    """Just enough of RDS, Auto Scaling, Beanstalk and SSM for the handler."""

    def __init__(self, db="stopped", instances=0, idle=None, params=None):
        self.db, self.instances, self.idle = db, instances, idle
        self.params = {"/cloud-dev-portal/mode": "hibernate", **(params or {})}
        self.calls = []

    def install(self, monkeypatch):
        rds = MagicMock()
        rds.describe_db_clusters.side_effect = lambda **_: {"DBClusters": [{"Status": self.db}]}
        rds.start_db_cluster.side_effect = lambda **_: self._call("start_db", db="starting")
        rds.stop_db_cluster.side_effect = lambda **_: self._call("stop_db", db="stopping")
        autoscaling = MagicMock()
        autoscaling.describe_auto_scaling_groups.side_effect = lambda **_: {
            "AutoScalingGroups": [{"DesiredCapacity": self.instances}]}
        autoscaling.update_auto_scaling_group.side_effect = lambda **kw: self._call(
            f"scale_{kw['DesiredCapacity']}", instances=kw["DesiredCapacity"])
        beanstalk = MagicMock()
        beanstalk.describe_environment_resources.return_value = {
            "EnvironmentResources": {"AutoScalingGroups": [{"Name": GROUP}]}}
        ssm = MagicMock()
        ssm.exceptions.ParameterNotFound = KeyError
        ssm.get_parameter.side_effect = lambda Name: {"Parameter": {"Value": self.params[Name]}}
        ssm.put_parameter.side_effect = lambda Name, Value, **_: self.params.__setitem__(Name, Value)
        for name, client in (("rds", rds), ("autoscaling", autoscaling), ("beanstalk", beanstalk), ("ssm", ssm)):
            monkeypatch.setattr(handler, name, client)
        monkeypatch.setattr(handler, "app_idle_seconds", lambda: self.idle)
        monkeypatch.setattr(handler.time, "time", lambda: NOW)
        return self

    def _call(self, name, **state):
        self.calls.append(name)
        for key, value in state.items():
            setattr(self, key, value)


@pytest.mark.parametrize("mode, woken_ago, idle, expected", [
    ("active", 10_000, 10_000, False),     # active never sleeps
    ("hibernate", 60, None, False),        # just woken: the app needs minutes to answer
    ("hibernate", 10_000, 600, False),     # someone used it 10 minutes ago
    ("hibernate", 10_000, 1800, True),     # idle for 30 minutes
    ("hibernate", 10_000, None, True),     # asleep already, or a failed wake
])
def test_when_the_tick_sleeps(mode, woken_ago, idle, expected):
    assert handler.should_sleep(mode, NOW - woken_ago, idle, NOW) is expected


def test_wake_starts_only_what_is_asleep(monkeypatch):
    aws = FakeAws(db="stopped", instances=0).install(monkeypatch)
    handler.wake()
    assert aws.calls == ["start_db", "scale_1"]
    assert aws.params["/cloud-dev-portal/woken-at"] == str(NOW)
    aws.calls.clear()
    handler.wake()  # the waking-up page asks again every 10 seconds: nothing more happens
    assert aws.calls == []


def test_sleep_waits_for_a_starting_database(monkeypatch):
    aws = FakeAws(db="starting", instances=1).install(monkeypatch)
    handler.sleep()
    assert aws.calls == ["scale_0"]  # the cluster can't stop until it is available
    aws.db = "available"
    handler.sleep()
    assert aws.calls == ["scale_0", "stop_db"]


def test_tick_in_hibernate_sleeps_an_idle_portal(monkeypatch):
    aws = FakeAws(db="available", instances=1, idle=3600,
                  params={"/cloud-dev-portal/woken-at": str(NOW - 7200)}).install(monkeypatch)
    handler.lambda_handler({"action": "tick"}, None)
    assert aws.calls == ["scale_0", "stop_db"]


def test_tick_in_active_mode_turns_back_on_what_aws_stopped(monkeypatch):
    aws = FakeAws(db="stopped", instances=1, params={"/cloud-dev-portal/mode": "active"}).install(monkeypatch)
    handler.lambda_handler({"action": "tick"}, None)
    assert aws.calls == ["start_db"]


def test_switching_modes(monkeypatch):
    aws = FakeAws(db="stopped", instances=0).install(monkeypatch)
    handler.lambda_handler({"mode": "active"}, None)
    assert aws.params["/cloud-dev-portal/mode"] == "active" and aws.calls == ["start_db", "scale_1"]
    aws.db = "available"
    handler.lambda_handler({"mode": "hibernate"}, None)
    assert aws.params["/cloud-dev-portal/mode"] == "hibernate" and aws.calls[-2:] == ["scale_0", "stop_db"]
    with pytest.raises(ValueError):
        handler.lambda_handler({"mode": "asleep"}, None)


def http(method, path):
    return {"requestContext": {"http": {"method": method}}, "rawPath": path}


def test_cloudfront_paths(monkeypatch):
    aws = FakeAws(db="stopped", instances=0).install(monkeypatch)
    page = handler.lambda_handler(http("GET", "/system"), None)
    assert page["statusCode"] == 503 and "Waking up" in page["body"] and aws.calls == []

    started = handler.lambda_handler(http("POST", "/_wake/start"), None)
    assert started["statusCode"] == 200 and aws.calls == ["start_db", "scale_1"]
    assert json.loads(started["body"])["ready"] is False

    aws.db, aws.idle = "available", 5
    assert json.loads(handler.lambda_handler(http("GET", "/_wake/status"), None)["body"])["ready"] is True


def test_the_committed_zip_matches_the_code():
    """infra/portal_mode.zip is what the manual setup uploads: rebuild it
    (python scripts/build_lambda_zip.py) whenever the function changes."""
    import zipfile
    root = Path(__file__).resolve().parent.parent
    with zipfile.ZipFile(root / "portal_mode.zip") as z:
        assert sorted(z.namelist()) == ["handler.py", "wake.html"]
        for name in z.namelist():
            assert z.read(name) == (root / "portal_mode" / name).read_bytes().replace(b"\r\n", b"\n"), name
