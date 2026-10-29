"""Command line: aiops ask "Why is the study-rag api not working?" """

import argparse
import os
import sys
import time

import httpx

from aiops import agent, config
from aiops.tools import kubectl


def preflight() -> list[str]:
    """Check the cluster and Ollama before starting, so a stale kubeconfig gives a clear hint."""
    problems = []
    if not os.path.exists(config.KUBECONFIG):
        problems.append(f"No agent kubeconfig at {config.KUBECONFIG}. Run: ./scripts/agent-kubeconfig.sh")
    elif kubectl.run_kubectl(["get", "--raw", "/readyz"]).startswith("ERROR"):
        problems.append(
            "Cluster not reachable with the agent's kubeconfig (minikube stopped, new port or expired token). "
            "Start minikube if needed, then run: ./scripts/agent-kubeconfig.sh"
        )
    try:
        tags = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json()
    except httpx.HTTPError:
        problems.append(f"Ollama not reachable at {config.OLLAMA_URL}. Start it: open -a Ollama")
    else:
        if config.CHAT_MODEL not in {m["name"] for m in tags.get("models", [])}:
            problems.append(f"Model {config.CHAT_MODEL} not found. Run: ollama pull {config.CHAT_MODEL}")
    return problems


def _format_args(arguments: dict | str) -> str:
    if isinstance(arguments, dict):
        return ", ".join(f"{k}={v}" for k, v in arguments.items())
    return str(arguments)


def _print_step(verbose: bool):
    def print_step(step: agent.Step) -> None:
        summary = step.result.splitlines()[0] if step.result.startswith("ERROR") else f"{len(step.result)} chars"
        print(f"  → {step.tool}({_format_args(step.arguments)})  [{summary}]")
        if verbose:
            print("    " + step.result.replace("\n", "\n    "))

    return print_step


def ask(question: str, max_steps: int | None, verbose: bool) -> int:
    problems = preflight()
    if problems:
        for problem in problems:
            print(f"✗ {problem}", file=sys.stderr)
        return 1

    print(f"Investigating with {config.CHAT_MODEL} ...")
    start = time.time()
    try:
        result = agent.run(question, max_steps=max_steps, on_step=_print_step(verbose))
    except httpx.HTTPError as e:
        print(f"✗ Ollama request failed: {e}", file=sys.stderr)
        return 1

    note = ", step limit reached" if result.hit_step_limit else ""
    print(f"\n{result.answer}\n\n({len(result.steps)} tool calls, {time.time() - start:.1f} s{note})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aiops", description="Explains problems in a Kubernetes cluster.")
    commands = parser.add_subparsers(dest="command", required=True)
    ask_parser = commands.add_parser("ask", help="ask a question about the cluster")
    ask_parser.add_argument("question")
    ask_parser.add_argument(
        "--max-steps", type=int, help=f"tool calls before it must answer (default {config.MAX_STEPS})"
    )
    ask_parser.add_argument("-v", "--verbose", action="store_true", help="also print the full tool output")
    args = parser.parse_args(argv)
    return ask(args.question, args.max_steps, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
