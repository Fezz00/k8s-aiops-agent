"""Tests for the tool menu and run_tool, with the kubectl functions replaced by fakes."""

import inspect

import pytest

from aiops.tools import registry


def test_every_tool_in_the_menu_has_a_function():
    names = [tool["function"]["name"] for tool in registry.TOOLS]
    assert sorted(names) == sorted(registry._FUNCTIONS)


@pytest.mark.parametrize("tool", registry.TOOLS, ids=lambda t: t["function"]["name"])
def test_schema_parameters_match_the_function(tool):
    schema = tool["function"]["parameters"]
    params = inspect.signature(registry._FUNCTIONS[tool["function"]["name"]]).parameters
    assert set(schema["properties"]) == set(params)
    required_in_code = {n for n, p in params.items() if p.default is inspect.Parameter.empty}
    assert set(schema["required"]) == required_in_code


@pytest.fixture
def fake_get_resources(monkeypatch):
    calls = []

    def fake(kind, namespace=None):
        calls.append((kind, namespace))
        return "pod list"

    monkeypatch.setitem(registry._FUNCTIONS, "get_resources", fake)
    return calls


def test_run_tool_calls_the_function(fake_get_resources):
    assert registry.run_tool("get_resources", {"kind": "pods", "namespace": "study-rag"}) == "pod list"
    assert fake_get_resources == [("pods", "study-rag")]


def test_arguments_as_json_string_are_parsed(fake_get_resources):
    registry.run_tool("get_resources", '{"kind": "pods"}')
    assert fake_get_resources == [("pods", None)]


def test_unknown_tool_returns_error():
    assert registry.run_tool("delete_pod", {"name": "api"}).startswith("ERROR: unknown tool 'delete_pod'")


@pytest.mark.parametrize("arguments", [{}, {"kind": "pods", "color": "red"}, "not json", ["pods"]])
def test_wrong_arguments_return_error(fake_get_resources, arguments):
    assert registry.run_tool("get_resources", arguments).startswith("ERROR:")
    assert fake_get_resources == []
