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
