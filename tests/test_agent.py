"""Tests for the agent loop, with a fake model that plays a scripted conversation: no Ollama, no cluster."""

import pytest

from aiops import agent, llm, prompts
from aiops.tools import registry


def tool_call(name, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def answer(text):
    return {"role": "assistant", "content": text}


class FakeModel:
    """Stands in for llm.chat: returns the scripted replies in order and remembers each request."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, messages, tools=None):
        self.requests.append({"messages": list(messages), "tools": tools})
        return self.replies.pop(0)


@pytest.fixture
def tool_calls(monkeypatch):
    calls = []

    def fake_run_tool(name, arguments):
        calls.append((name, arguments))
        return f"result of {name}"

    monkeypatch.setattr(registry, "run_tool", fake_run_tool)
    return calls


def use_model(monkeypatch, replies):
    model = FakeModel(replies)
    monkeypatch.setattr(llm, "chat", model)
    return model


def test_answer_without_tools(monkeypatch, tool_calls):
    model = use_model(monkeypatch, [answer("No problem found.")])
    result = agent.run("Is everything fine?")
    assert result.answer == "No problem found."
    assert result.steps == [] and tool_calls == []
    first = model.requests[0]
    assert first["messages"][0] == {"role": "system", "content": prompts.SYSTEM_PROMPT}
    assert first["messages"][1] == {"role": "user", "content": "Is everything fine?"}
    assert first["tools"] == registry.TOOLS


def test_tool_result_goes_back_to_the_model(monkeypatch, tool_calls):
    model = use_model(monkeypatch, [tool_call("get_resources", kind="pods", namespace="aiops-lab"), answer("Done.")])
    seen = []
    result = agent.run("Why is aiops-lab broken?", on_step=seen.append)

    assert tool_calls == [("get_resources", {"kind": "pods", "namespace": "aiops-lab"})]
    assert result.answer == "Done."
    assert [s.tool for s in result.steps] == ["get_resources"] == [s.tool for s in seen]
    second = model.requests[1]["messages"]
    assert second[-2]["tool_calls"][0]["function"]["name"] == "get_resources"
    assert second[-1] == {"role": "tool", "tool_name": "get_resources", "content": "result of get_resources"}


def test_several_tool_calls_in_one_reply(monkeypatch, tool_calls):
    both = tool_call("get_events", namespace="x")
    both["tool_calls"] += tool_call("get_resources", kind="pods")["tool_calls"]
    use_model(monkeypatch, [both, answer("Done.")])
    result = agent.run("?")
    assert [name for name, _ in tool_calls] == ["get_events", "get_resources"]
    assert len(result.steps) == 2


def test_step_limit_forces_an_answer_without_tools(monkeypatch, tool_calls):
    endless = [tool_call("get_resources", kind="pods") for _ in range(3)]
    model = use_model(monkeypatch, [*endless, answer("Best guess.")])
    result = agent.run("?", max_steps=3)

    assert len(tool_calls) == 3
    assert result.hit_step_limit
    assert result.answer == "Best guess."
    last = model.requests[-1]
    assert last["tools"] is None
    assert last["messages"][-1] == {"role": "user", "content": prompts.STEP_LIMIT_REACHED}
