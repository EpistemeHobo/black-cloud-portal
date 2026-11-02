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
    "AdminEmail": "a@b.c"}.items()]
MISSING = ClientError({"Error": {"Message": "Stack with id gargantua does not exist"}}, "DescribeStacks")


def fake_cfn(*states):
    """A client whose describe_stacks walks through these statuses; None = no stack."""
    cfn = MagicMock()
    answers = [MISSING if s is None else {"Stacks": [{"StackStatus": s, "Outputs": OUTPUTS}]} for s in states]
    cfn.describe_stacks.side_effect = answers
    return cfn


def fake_eb(env_answers=(), app=False):
    """Beanstalk with an environment for as many checks as env_answers says."""
    eb = MagicMock()
    answers = [{"Environments": [{"EnvironmentName": "cloud-dev"}] if present else []} for present in env_answers]
    eb.describe_environments.side_effect = answers + [{"Environments": []}] * 5
    eb.describe_applications.return_value = {"Applications": [{"ApplicationName": "cloud-dev-portal"}] if app else []}
    return eb


def test_the_template_carries_the_built_sign_in_background_and_stays_small_enough():
    import base64
    import re
    root = Path(__file__).resolve().parent.parent
    template = (root / "full-stack.yaml").read_bytes()
    assert len(template) <= 51200, "too big to send directly to CloudFormation"
    encoded = re.search(rb"Bytes: (\S+)", template).group(1)
    assert base64.b64decode(encoded) == (root / "signin-background.svg").read_bytes()


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
    assert portal_stack.main(["delete"], cfn, fake_eb()) == 1
    cfn.delete_stack.assert_not_called()


def test_delete_waits_until_the_stack_is_gone(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda prompt: "gargantua")
    cfn = fake_cfn("CREATE_COMPLETE", "DELETE_IN_PROGRESS", None)
    cfn.list_stacks.return_value = {"StackSummaries": []}
    assert portal_stack.main(["delete"], cfn, fake_eb()) == 0
    cfn.delete_stack.assert_called_once_with(StackName="gargantua")
    assert "gone" in capsys.readouterr().out


def test_a_failed_delete_is_reported():
    cfn = fake_cfn("CREATE_COMPLETE", "DELETE_FAILED")
    cfn.describe_stack_events.return_value = {"StackEvents": [
        {"LogicalResourceId": "DocsBucket", "ResourceStatus": "DELETE_FAILED", "ResourceStatusReason": "not empty"}]}
    assert portal_stack.main(["delete", "--yes"], cfn, fake_eb()) == 1


def test_delete_removes_what_an_interrupted_delete_left(capsys):
    cfn = fake_cfn("CREATE_COMPLETE", "DELETE_IN_PROGRESS", None)
    cfn.list_stacks.return_value = {"StackSummaries": [{"StackName": "awseb-e-abc-stack"}, {"StackName": "other"}]}
    eb = fake_eb([True, True, True], app=True)
    assert portal_stack.main(["delete", "--yes"], cfn, eb) == 0
    eb.terminate_environment.assert_called_once_with(EnvironmentName="cloud-dev")
    eb.delete_application.assert_called_once_with(ApplicationName="cloud-dev-portal", TerminateEnvByForce=True)
    cfn.delete_stack.assert_any_call(StackName="awseb-e-abc-stack")
    assert "other" not in str(cfn.delete_stack.call_args_list)


def test_without_a_stack_leftovers_need_confirming_even_with_yes(monkeypatch, capsys):
    # They could be a hand-built Lab 1, so --yes isn't enough here.
    answers = []
    monkeypatch.setattr("builtins.input", lambda prompt: answers.append(prompt) or "no")
    cfn = fake_cfn(None)
    cfn.list_stacks.return_value = {"StackSummaries": []}
    eb = fake_eb([True])
    assert portal_stack.main(["delete", "--yes"], cfn, eb) == 1
    assert answers and "Lab 1" in capsys.readouterr().out
    eb.terminate_environment.assert_not_called()


def test_status_mentions_leftovers(capsys):
    cfn = fake_cfn(None)
    cfn.list_stacks.return_value = {"StackSummaries": []}
    assert portal_stack.main(["status"], cfn, fake_eb([True])) == 0
    assert "environment cloud-dev" in capsys.readouterr().out


@pytest.mark.parametrize("code, message", [
    ("AccessDenied", "not authorized with an explicit deny in a service control policy"),
    ("AccessDenied", "not authorized with an explicit deny in an identity-based policy: voc-cancel-cred"),
    ("ExpiredToken", "The security token included in the request is expired"),
])
def test_a_lab_session_ending_gets_a_clear_message(code, message, capsys):
    cfn = fake_cfn("CREATE_COMPLETE")
    cfn.describe_stacks.side_effect = ClientError({"Error": {"Code": code, "Message": message}}, "DescribeStacks")
    assert portal_stack.main(["status"], cfn, fake_eb()) == 1
    assert "lab session has ended" in capsys.readouterr().out


def test_other_errors_are_not_blamed_on_the_session():
    cfn = fake_cfn("CREATE_COMPLETE")
    cfn.describe_stacks.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "no identity-based policy allows it"}}, "DescribeStacks")
    with pytest.raises(ClientError):
        portal_stack.main(["status"], cfn, fake_eb())


@pytest.mark.parametrize("argv", [[], ["create"], ["create", "not-an-email"], ["delete", "now"], ["other"]])
def test_wrong_usage_touches_nothing(argv):
    cfn = MagicMock()
    assert portal_stack.main(argv, cfn, MagicMock()) == 2
    assert not cfn.method_calls
