"""Tests for the kubectl tools, with kubectl replaced by a fake: no cluster needed."""

import subprocess

import pytest

from aiops import config
from aiops.tools import kubectl


class FakeKubectl:
    """Stands in for subprocess.run: remembers each command and returns a prepared answer."""

    def __init__(self, stdout="ok", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": cmd, **kwargs})
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)

    @property
    def last_cmd(self):
        return self.calls[-1]["cmd"]


@pytest.fixture
def fake(monkeypatch):
    fake = FakeKubectl()
    monkeypatch.setattr(kubectl.subprocess, "run", fake)
    return fake


def test_get_resources_builds_command(fake):
    kubectl.get_resources("pods", "study-rag")
    assert fake.last_cmd == ["kubectl", "get", "pods", "-o", "wide", "-n", "study-rag"]


@pytest.mark.parametrize("alias", ["pod", "po", "Pods", " pods "])
def test_kind_aliases_resolve_to_full_name(fake, alias):
    kubectl.get_resources(alias, "study-rag")
    assert fake.last_cmd[2] == "pods"


def test_no_namespace_means_all_namespaces(fake):
    kubectl.get_resources("deploy")
    assert fake.last_cmd == ["kubectl", "get", "deployments", "-o", "wide", "--all-namespaces"]


def test_runs_with_agent_kubeconfig_without_shell(fake):
    kubectl.get_resources("pods", "study-rag")
    call = fake.calls[-1]
    assert call["env"]["KUBECONFIG"] == config.KUBECONFIG
    assert not call.get("shell")
    assert call["timeout"] == config.KUBECTL_TIMEOUT


def test_secrets_are_rejected(fake):
    result = kubectl.get_resources("secrets", "monitoring")
    assert result.startswith("ERROR: kind 'secrets' is not allowed")
    assert fake.calls == []


@pytest.mark.parametrize(
    "bad_name", ["--kubeconfig=/Users/me/.kube/config", "-o=yaml", "api pod", "API", "a;rm -rf /", ""]
)
def test_flags_and_odd_names_are_rejected(fake, bad_name):
    result = kubectl.describe("pod", bad_name, "study-rag")
    assert result.startswith("ERROR:")
    assert fake.calls == []


def test_describe_without_namespace(fake):
    kubectl.describe("node", "study-rag")
    assert fake.last_cmd == ["kubectl", "describe", "nodes", "study-rag"]


def test_get_events_sorted_by_time(fake):
    kubectl.get_events("aiops-lab")
    assert fake.last_cmd == ["kubectl", "get", "events", "--sort-by=.lastTimestamp", "-n", "aiops-lab"]


def test_get_logs_with_all_options(fake):
    kubectl.get_logs("api-55f4", "study-rag", container="api", previous=True, tail=50)
    assert fake.last_cmd == ["kubectl", "logs", "api-55f4", "-n", "study-rag", "--tail=50", "-c", "api", "--previous"]


@pytest.mark.parametrize(("asked", "used"), [(10_000, kubectl.MAX_LOG_LINES), (0, 1), (-5, 1)])
def test_get_logs_tail_is_limited(fake, asked, used):
    kubectl.get_logs("api-55f4", "study-rag", tail=asked)
    assert f"--tail={used}" in fake.last_cmd


def test_kubectl_error_comes_back_as_text(monkeypatch):
    fake = FakeKubectl(stdout="", stderr='Error from server (NotFound): pods "xyz" not found\n', returncode=1)
    monkeypatch.setattr(kubectl.subprocess, "run", fake)
    assert kubectl.describe("pod", "xyz", "study-rag") == 'ERROR: Error from server (NotFound): pods "xyz" not found'


def test_kubectl_error_keeps_only_the_last_line(monkeypatch):
    noise = 'E1029 memcache.go:265] "Unhandled Error" err="couldn\'t get current server API group list"\n' * 5
    message = "The connection to the server 127.0.0.1:56648 was refused - did you specify the right host or port?"
    monkeypatch.setattr(kubectl.subprocess, "run", FakeKubectl(stdout="", stderr=noise + message, returncode=1))
    assert kubectl.get_resources("pods", "study-rag") == f"ERROR: {message}"


def test_no_resources_message_from_stderr_is_returned(monkeypatch):
    fake = FakeKubectl(stdout="", stderr="No resources found in aiops-lab namespace.\n")
    monkeypatch.setattr(kubectl.subprocess, "run", fake)
    assert kubectl.get_resources("pods", "aiops-lab") == "No resources found in aiops-lab namespace."


def test_timeout_comes_back_as_text(monkeypatch):
    def too_slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(kubectl.subprocess, "run", too_slow)
    assert kubectl.get_resources("pods", "study-rag").startswith("ERROR: kubectl timed out")


def test_long_output_is_cut_and_keeps_both_ends():
    text = "START" + "x" * 10_000 + "END"
    cut = kubectl.truncate(text, 600)
    assert cut.startswith("START")
    assert cut.endswith("END")
    assert "characters cut" in cut
    assert len(cut) < 700


def test_short_output_is_unchanged():
    assert kubectl.truncate("short", 600) == "short"
