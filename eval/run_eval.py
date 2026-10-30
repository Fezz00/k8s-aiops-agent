"""Breaks the cluster on purpose, lets the agent investigate, and scores its answers.

For each scenario in scenarios/:
    1. apply manifest.yaml (as admin – only the test harness may change the cluster)
    2. wait until the failure shows
    3. ask the agent the scenario's question, --runs times (as the read-only agent, as always)
    4. score each answer against expected.yaml
    5. delete the scenario again

    python -m eval.run_eval                 all scenarios, 3 runs each
    python -m eval.run_eval --only 02 --runs 1

Needs the cluster and Ollama, so it runs locally, not in CI. Full conversations are saved in eval/results/.
"""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import yaml

from aiops import agent, config
from eval.scoring import score

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "scenarios"
RESULTS_DIR = ROOT / "eval" / "results"
ADMIN_CONTEXT = os.getenv("ADMIN_CONTEXT", "study-rag")  # your admin context, not the agent's kubeconfig
LAB_NAMESPACE = "aiops-lab"


def admin_kubectl(*args: str) -> None:
    subprocess.run(["kubectl", "--context", ADMIN_CONTEXT, *args], check=True, capture_output=True, text=True)


def remove_scenarios() -> None:
    """Delete everything a scenario created in the lab namespace, and wait until the pods are gone."""
    admin_kubectl("delete", "deployments", "-n", LAB_NAMESPACE, "-l", "aiops-scenario", "--ignore-not-found")
    admin_kubectl("wait", "--for=delete", "pods", "-n", LAB_NAMESPACE, "-l", "aiops-scenario", "--timeout=60s")


def run_scenario(path: Path, runs: int) -> list[dict]:
    expected = yaml.safe_load((path / "expected.yaml").read_text())
    remove_scenarios()
    admin_kubectl("apply", "-f", str(path / "manifest.yaml"))
    print(f"\n{path.name}: applied, waiting {expected['wait_seconds']} s for the failure to show ...")
    time.sleep(expected["wait_seconds"])

    results = []
    try:
        for i in range(1, runs + 1):
            start = time.time()
            run = agent.run(expected["question"])
            seconds = time.time() - start
            result = score(run.answer, expected["must_mention"])
            print(
                f"  run {i}: {'PASS' if result['passed'] else 'FAIL'}  "
                f"{len(run.steps)} tool calls  {seconds:.1f} s  "
                f"tools: {', '.join(s.tool for s in run.steps) or '-'}"
                + (f"  missing: {result['missing']}" if result["missing"] else "")
            )
            results.append(
                {
                    "scenario": path.name,
                    "run": i,
                    **result,
                    "tool_calls": len(run.steps),
                    "seconds": round(seconds, 1),
                    "hit_step_limit": run.hit_step_limit,
                    "answer": run.answer,
                    "messages": run.messages,
                }
            )
    finally:
        remove_scenarios()
    return results


def print_summary(results: list[dict]) -> None:
    print(f"\nModel: {config.CHAT_MODEL}\n")
    print(f"{'scenario':<16} {'passed':>7} {'avg tool calls':>15} {'avg seconds':>12} {'step limit':>11}")
    for name in sorted({r["scenario"] for r in results}):
        rows = [r for r in results if r["scenario"] == name]
        passed = sum(r["passed"] for r in rows)
        print(
            f"{name:<16} {f'{passed}/{len(rows)}':>7} "
            f"{sum(r['tool_calls'] for r in rows) / len(rows):>15.1f} "
            f"{sum(r['seconds'] for r in rows) / len(rows):>12.1f} "
            f"{sum(r['hit_step_limit'] for r in rows):>11}"
        )
    total = sum(r["passed"] for r in results)
    print(f"{'total':<16} {f'{total}/{len(results)}':>7}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the broken-cluster scenarios and score the agent.")
    parser.add_argument("--runs", type=int, default=3, help="answers per scenario (LLM answers vary)")
    parser.add_argument("--only", help="run only scenarios whose folder starts with this, e.g. 02")
    args = parser.parse_args()

    paths = sorted(p for p in SCENARIOS_DIR.iterdir() if (p / "expected.yaml").exists())
    if args.only:
        paths = [p for p in paths if p.name.startswith(args.only)]

    results = [r for path in paths for r in run_scenario(path, args.runs)]
    print_summary(results)

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{config.CHAT_MODEL.replace(':', '_')}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nFull conversations: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
