"""The tool menu: what the model is told about each tool, and which Python function runs it.

The model only sees TOOLS (names, descriptions, parameters as JSON Schema). It chooses a tool
from the description text alone, so the descriptions matter as much as the code.
"""

import json

from aiops.tools import kubectl


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_KIND = {"type": "string", "description": "Resource type, e.g. pods, deployments, services, events, nodes"}
_NAMESPACE = {"type": "string", "description": "Namespace, e.g. study-rag"}

TOOLS = [
    _tool(
        "get_resources",
        "List resources of one kind with their status, e.g. all pods with READY, STATUS and RESTARTS. "
        "Start here. Leave out namespace to list all namespaces.",
        {"kind": _KIND, "namespace": _NAMESPACE},
        ["kind"],
    ),
    _tool(
        "describe",
        "Details of one resource: containers, probes, limits, conditions and its recent events "
        "(e.g. OOMKilled, ImagePullBackOff, failed readiness probe).",
        {"kind": _KIND, "name": {"type": "string", "description": "Exact resource name"}, "namespace": _NAMESPACE},
        ["kind", "name"],
    ),
    _tool(
        "get_events",
        "Events in a namespace sorted by time, newest last: scheduling, pulls, probe failures, kills.",
        {"namespace": _NAMESPACE},
        [],
    ),
    _tool(
        "get_logs",
        "Last log lines of a pod. Use previous=true to read the log of the container that crashed "
        "before the current one (needed for CrashLoopBackOff).",
        {
            "pod": {"type": "string", "description": "Exact pod name"},
            "namespace": _NAMESPACE,
            "container": {"type": "string", "description": "Container name, only for pods with several containers"},
            "previous": {"type": "boolean", "description": "true = log of the previous, crashed container"},
            "tail": {"type": "integer", "description": "Number of lines from the end (default 100)"},
        },
        ["pod", "namespace"],
    ),
]

_FUNCTIONS = {
    "get_resources": kubectl.get_resources,
    "describe": kubectl.describe,
    "get_events": kubectl.get_events,
    "get_logs": kubectl.get_logs,
}


def run_tool(name: str, arguments: dict | str) -> str:
    """Run the tool the model asked for. Mistakes come back as "ERROR: ..." for the model to read."""
    func = _FUNCTIONS.get(name)
    if func is None:
        return f"ERROR: unknown tool {name!r}. Available tools: {', '.join(_FUNCTIONS)}"
    if isinstance(arguments, str):  # some models send the arguments as a JSON string
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return f"ERROR: arguments for {name} are not valid JSON: {arguments!r}"
    if not isinstance(arguments, dict):
        return f"ERROR: arguments for {name} must be a JSON object"
    try:
        return func(**arguments)
    except (TypeError, AttributeError) as e:  # missing, unknown or wrongly typed arguments
        return f"ERROR: wrong arguments for {name}: {e}"
