"""All settings in one place.

Each value comes from an environment variable, with a default for local development.
"""

import os

# kubeconfig of the read-only ServiceAccount, written by scripts/agent-kubeconfig.sh
# (outside the repo, because it holds a token)
KUBECONFIG = os.path.expanduser(os.getenv("AIOPS_KUBECONFIG", "~/.kube/aiops-agent.yaml"))
KUBECTL_TIMEOUT = int(os.getenv("KUBECTL_TIMEOUT", "20"))  # seconds per kubectl call

# Tool output longer than this is cut, so a huge log doesn't fill the model's context window
MAX_OUTPUT_CHARS = int(os.getenv("MAX_OUTPUT_CHARS", "6000"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:4b-instruct")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))  # seconds per model reply
# Context window in tokens. If the conversation gets longer, Ollama silently drops the oldest part:
# the system prompt with all the rules. Several tool results of up to MAX_OUTPUT_CHARS need room.
NUM_CTX = int(os.getenv("NUM_CTX", "16384"))

# Tool calls per question before the agent has to answer with what it found
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
