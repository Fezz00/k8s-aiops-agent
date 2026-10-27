# K8s AIOps Agent

An assistant that explains problems in a Kubernetes cluster. Ask it a question in plain words, e.g. *"Why is the app in namespace aiops-lab not working?"*. It decides itself which read-only tools to call (`kubectl get / describe / logs`, events, Prometheus queries), reads the results and explains what is wrong and how to fix it.

- **Plain Python** – no LangChain or LlamaIndex; the agent loop is a few lines you can read.
- **Local LLM** – `qwen3:4b-instruct` via [Ollama](https://ollama.com) with tool calling.
- **Read-only by design** – the agent has its own Kubernetes ServiceAccount that can look, not change (and cannot read Secrets).

> **Status:** Phase 0 – setup.
