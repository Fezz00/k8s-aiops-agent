#!/usr/bin/env bash
# Writes a kubeconfig for the read-only ServiceAccount aiops-agent (rbac/agent-rbac.yaml).
# Run it after every "minikube start" (the API server port changes) or when the token expired.
#
#   ./scripts/agent-kubeconfig.sh        token valid 24h
#   ./scripts/agent-kubeconfig.sh 8h     token valid 8h
#
# The file is written outside the repo, because it contains the token.
set -euo pipefail

ADMIN_CONTEXT="${ADMIN_CONTEXT:-study-rag}"           # your normal admin context, used once to create the token
OUT="${AIOPS_KUBECONFIG:-$HOME/.kube/aiops-agent.yaml}"
DURATION="${1:-24h}"

if ! kubectl --context "$ADMIN_CONTEXT" get --raw /readyz >/dev/null 2>&1; then
  echo "Cluster not reachable with context '$ADMIN_CONTEXT'. Start it first: minikube start -p study-rag" >&2
  exit 1
fi

server=$(kubectl config view --minify --context "$ADMIN_CONTEXT" -o jsonpath='{.clusters[0].cluster.server}')
ca_file=$(kubectl config view --minify --context "$ADMIN_CONTEXT" -o jsonpath='{.clusters[0].cluster.certificate-authority}')
ca_data=$(base64 < "$ca_file" | tr -d '\n')
token=$(kubectl --context "$ADMIN_CONTEXT" create token aiops-agent -n aiops-agent --duration="$DURATION")

# umask 077: the new file is readable only by you (chmod 600)
umask 077
cat > "$OUT" <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: study-rag
    cluster:
      server: $server
      certificate-authority-data: $ca_data
users:
  - name: aiops-agent
    user:
      token: $token
contexts:
  - name: aiops-agent
    context:
      cluster: study-rag
      user: aiops-agent
current-context: aiops-agent
EOF

echo "Wrote $OUT (server $server, token valid $DURATION)"
echo "Check as the agent:"
echo "  read pods:   $(kubectl --kubeconfig "$OUT" auth can-i list pods -n study-rag)"
echo "  delete pods: $(kubectl --kubeconfig "$OUT" auth can-i delete pods -n study-rag)"
echo "  get secrets: $(kubectl --kubeconfig "$OUT" auth can-i get secrets -n study-rag)"
