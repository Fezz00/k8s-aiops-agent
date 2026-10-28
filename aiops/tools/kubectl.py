"""Read-only kubectl tools.

Two layers keep them read-only:
1. Cluster: kubectl runs with the agent's kubeconfig (ServiceAccount with the "view" role, see rbac/).
2. Code: only a few fixed commands are built, and every argument is checked first, so a model
   can't pass other commands or flags (e.g. a "name" like "--kubeconfig=...").

Errors come back as text starting with "ERROR:" instead of exceptions: the model reads them
and can try something else.
"""

import functools
import os
import re
import subprocess

from aiops import config

# Resource types the agent may look at, with the short names kubectl also accepts.
# Secrets are left out on purpose (the RBAC role can't read them either).
KINDS = {
    "pods": ["pod", "po"],
    "deployments": ["deployment", "deploy"],
    "replicasets": ["replicaset", "rs"],
    "statefulsets": ["statefulset", "sts"],
    "daemonsets": ["daemonset", "ds"],
    "jobs": ["job"],
    "cronjobs": ["cronjob", "cj"],
    "services": ["service", "svc"],
    "endpoints": ["ep"],
    "ingresses": ["ingress", "ing"],
    "configmaps": ["configmap", "cm"],
    "persistentvolumeclaims": ["persistentvolumeclaim", "pvc"],
    "persistentvolumes": ["persistentvolume", "pv"],
    "storageclasses": ["storageclass", "sc"],
    "nodes": ["node", "no"],
    "namespaces": ["namespace", "ns"],
    "events": ["event", "ev"],
}
_KIND_BY_ALIAS = {alias: kind for kind, aliases in KINDS.items() for alias in [kind, *aliases]}

# Kubernetes names: lowercase letters, digits, "-" and ".", starting and ending with a letter or digit.
# A leading "-" is impossible, so a name can never be read as a flag.
_NAME = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$")

MAX_LOG_LINES = 500


def _check_kind(kind: str) -> str:
    resolved = _KIND_BY_ALIAS.get(kind.strip().lower())
    if resolved is None:
        raise ValueError(f"kind {kind!r} is not allowed. Allowed: {', '.join(KINDS)}")
    return resolved


def _check_name(value: str, what: str) -> str:
    if not _NAME.match(value):
        raise ValueError(f"{what} {value!r} is not a valid Kubernetes name")
    return value


def _namespace_args(namespace: str | None) -> list[str]:
    if namespace is None:
        return ["--all-namespaces"]
    return ["-n", _check_name(namespace, "namespace")]


def truncate(text: str, max_chars: int) -> str:
    """Keep the start and (larger) end of a long text: the newest log lines and events are at the end."""
    if len(text) <= max_chars:
        return text
    head = max_chars // 3
    tail = max_chars - head
    cut = len(text) - head - tail
    return f"{text[:head]}\n... [{cut} characters cut] ...\n{text[-tail:]}"


def run_kubectl(args: list[str]) -> str:
    """Run kubectl as the read-only agent. Always a list, never a shell string."""
    env = {**os.environ, "KUBECONFIG": config.KUBECONFIG}
    try:
        result = subprocess.run(
            ["kubectl", *args], capture_output=True, text=True, timeout=config.KUBECTL_TIMEOUT, env=env
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: kubectl timed out after {config.KUBECTL_TIMEOUT} s"
    except FileNotFoundError:
        return "ERROR: kubectl is not installed"
    if result.returncode != 0:
        return f"ERROR: {result.stderr.strip()}"
    # "No resources found" goes to stderr with exit code 0
    output = result.stdout.strip() or result.stderr.strip() or "(no output)"
    return truncate(output, config.MAX_OUTPUT_CHARS)


def _errors_as_text(func):
    """Turn a rejected argument into an "ERROR: ..." answer the model can read."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return f"ERROR: {e}"

    return wrapper


@_errors_as_text
def get_resources(kind: str, namespace: str | None = None) -> str:
    """List resources of one kind, e.g. all pods with status and restarts. No namespace = all namespaces."""
    return run_kubectl(["get", _check_kind(kind), "-o", "wide", *_namespace_args(namespace)])


@_errors_as_text
def describe(kind: str, name: str, namespace: str | None = None) -> str:
    """Details of one resource, including its recent events (e.g. OOMKilled, failed probes, pull errors)."""
    args = ["describe", _check_kind(kind), _check_name(name, "name")]
    if namespace is not None:
        args += ["-n", _check_name(namespace, "namespace")]
    return run_kubectl(args)


@_errors_as_text
def get_events(namespace: str | None = None) -> str:
    """Events sorted by time, newest last. No namespace = all namespaces."""
    return run_kubectl(["get", "events", "--sort-by=.lastTimestamp", *_namespace_args(namespace)])


@_errors_as_text
def get_logs(pod: str, namespace: str, container: str | None = None, previous: bool = False, tail: int = 100) -> str:
    """Last log lines of a pod. previous=True: log of the container that crashed before the current one."""
    tail = max(1, min(int(tail), MAX_LOG_LINES))
    args = ["logs", _check_name(pod, "pod"), "-n", _check_name(namespace, "namespace"), f"--tail={tail}"]
    if container is not None:
        args += ["-c", _check_name(container, "container")]
    if previous:
        args.append("--previous")
    return run_kubectl(args)
