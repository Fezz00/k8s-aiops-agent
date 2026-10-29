"""Talks to the local model through Ollama's chat API (POST /api/chat)."""

import httpx

from aiops import config


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Send the whole conversation (and the tool menu) and return the model's reply message.

    The reply has either "tool_calls" (the model wants tools to run) or only "content" (its answer).
    """
    payload = {
        "model": config.CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": config.NUM_CTX},
    }
    if tools:
        payload["tools"] = tools
    response = httpx.post(f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=config.LLM_TIMEOUT)
    response.raise_for_status()
    return response.json()["message"]
