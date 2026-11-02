"""scripts/portal_stack.py, with CloudFormation faked. Run: python -m pytest infra"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import portal_stack  # noqa: E402

OUTPUTS = [{"OutputKey": k, "OutputValue": v} for k, v in {
    "PortalUrl": "https://portal", "LauncherUrl": "https://portal/launch",
    "AdminEmail": "a@b.c", "AdminPasswordSecret": "arn:secret"}.items()]
MISSING = ClientError({"Error": {"Message": "Stack with id gargantua does not exist"}}, "DescribeStacks")


def fake_cfn(*states):
    """A client whose describe_stacks walks through these statuses; None = no stack."""
    cfn = MagicMock()
    answers = [MISSING if s is None else {"Stacks": [{"StackStatus": s, "Outputs": OUTPUTS}]} for s in states]
    cfn.describe_stacks.side_effect = answers
    return cfn


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(portal_stack, "POLL_SECONDS", 0)
    monkeypatch.setattr(portal_stack, "answers", lambda url: True)


def test_create_uploads_the_template_and_waits_for_the_portal(capsys):
    cfn = fake_cfn(None, "CREATE_IN_PROGRESS", "CREATE_COMPLETE")
    assert portal_stack.main(["create", "a@b.c"], cfn) == 0
    sent = cfn.create_stack.call_args.kwargs
    assert sent["StackName"] == "gargantua" and "AWS::RDS::DBCluster" in sent["TemplateBody"]
    assert sent["Parameters"] == [{"ParameterKey": "AdminEmail", "ParameterValue": "a@b.c"}]
    assert "https://portal/launch" in capsys.readouterr().out


def test_create_complete_is_not_success_if_the_app_never_answers(monkeypatch, capsys):
    monkeypatch.setattr(portal_stack, "answers", lambda url: False)
    monkeypatch.setattr(portal_stack, "APP_WAIT_SECONDS", 0)
    assert portal_stack.main(["create", "a@b.c"], fake_cfn(None, "CREATE_COMPLETE")) == 1
    assert "failed to start" in capsys.readouterr().out


def test_create_refuses_when_the_stack_exists():
    cfn = fake_cfn("CREATE_COMPLETE")
    assert portal_stack.main(["create", "a@b.c"], cfn) == 1
    cfn.create_stack.assert_not_called()


def test_delete_needs_the_stack_name_typed(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    cfn = fake_cfn("CREATE_COMPLETE")
    assert portal_stack.main(["delete"], cfn) == 1
    cfn.delete_stack.assert_not_called()


def test_delete_waits_until_the_stack_is_gone(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt: "gargantua")
    cfn = fake_cfn("CREATE_COMPLETE", "DELETE_IN_PROGRESS", None)
    assert portal_stack.main(["delete"], cfn) == 0
    cfn.delete_stack.assert_called_once_with(StackName="gargantua")
    assert "gone" in capsys.readouterr().out


def test_a_failed_delete_is_reported():
    cfn = fake_cfn("CREATE_COMPLETE", "DELETE_FAILED")
    cfn.describe_stack_events.return_value = {"StackEvents": [
        {"LogicalResourceId": "DocsBucket", "ResourceStatus": "DELETE_FAILED", "ResourceStatusReason": "not empty"}]}
    assert portal_stack.main(["delete", "--yes"], cfn) == 1


@pytest.mark.parametrize("argv", [[], ["create"], ["create", "not-an-email"], ["delete", "now"], ["other"]])
def test_wrong_usage_touches_nothing(argv):
    cfn = MagicMock()
    assert portal_stack.main(argv, cfn) == 2
    assert not cfn.method_calls
