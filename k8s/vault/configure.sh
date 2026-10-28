#!/usr/bin/env bash
# Configure Vault for the invest namespace: policy + Kubernetes auth + role.
# Safe to re-run. Uses the root token from macOS Keychain, passed over stdin
# (never in argv, never printed). Vault must be unsealed.
set -euo pipefail
cd "$(dirname "$0")"

# Run a vault command inside vault-0, authenticated as root.
# Line 1 of stdin = root token; anything after it is the command's own stdin.
vault_root() {
  { security find-generic-password -a vault -s kind-invest-vault-root -w; cat; } |
    kubectl exec -i -n vault vault-0 -- sh -c 'read -r VAULT_TOKEN; export VAULT_TOKEN; '"$1"
}

echo "1. Policy invest-read: read secret/data/invest/* only"
vault_root 'vault policy write invest-read -' < policies/invest-read.hcl

echo "2. Kubernetes auth method (Vault validates SA tokens via the TokenReview API)"
vault_root 'vault auth list | grep -q "^kubernetes/" || vault auth enable kubernetes' < /dev/null
# Running in-cluster, Vault uses its own SA token + CA to call the API server.
vault_root 'vault write auth/kubernetes/config kubernetes_host=https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT' < /dev/null

echo "3. Role invest-eso: SA invest/eso-vault, audience vault -> policy invest-read, 15m tokens"
vault_root 'vault write auth/kubernetes/role/invest-eso \
  bound_service_account_names=eso-vault \
  bound_service_account_namespaces=invest \
  audience=vault \
  token_policies=invest-read \
  token_ttl=15m' < /dev/null
