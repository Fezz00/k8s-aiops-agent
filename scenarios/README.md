# Scenarios

Broken workloads for testing the agent. Each folder has a `manifest.yaml` (the breakage, always in namespace `aiops-lab`, which Argo CD doesn't manage) and an `expected.yaml` (the question for the agent and the keywords a correct answer must contain).

| # | Scenario | What is broken | Where the cause is visible |
|---|---|---|---|
| 01 | ImagePullBackOff | Image tag typo `nginx:1.277` | `describe` / events: tag not found |
| 02 | CrashLoopBackOff | Postgres started without `POSTGRES_PASSWORD` | Only in the logs (`get_logs`, ideally `previous=true`) |
| 03 | OOMKilled | Memory limit 32Mi, the process keeps growing | `describe`: last state `OOMKilled` |

Run all of them and score the agent with `python -m eval.run_eval`. To try one by hand (with your admin kubeconfig):

```bash
kubectl apply -f scenarios/02-crashloop/manifest.yaml
aiops ask "The orders-db in namespace aiops-lab keeps failing. Why?"
kubectl delete deployments -n aiops-lab -l aiops-scenario
```
