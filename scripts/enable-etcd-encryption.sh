#!/usr/bin/env bash
# Turn on encryption at rest for Secrets in the kind cluster (secretbox, local key).
# The key is generated ON the control-plane node and never leaves it (never printed,
# never in git). Safe to re-run: skips steps already done.
#
# Limitation: the key sits on the node next to etcd, so this protects etcd backups and
# disk snapshots, not someone with root on the node. Production: KMS v2 provider.
set -euo pipefail
NODE=invest-control-plane

echo "1. Encryption config with a fresh 32-byte key (stays on $NODE)"
docker exec -i "$NODE" sh -s <<'EOF'
set -e
CFG=/etc/kubernetes/pki/encryption/config.yaml   # pki/ is already mounted into the API server
if [ -f "$CFG" ]; then echo "   exists, keeping current key"; exit 0; fi
mkdir -p /etc/kubernetes/pki/encryption
umask 077
KEY=$(head -c 32 /dev/urandom | base64)
cat > "$CFG" <<YAML
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources: [secrets]
    providers:
      - secretbox:            # first provider = used for NEW writes
          keys:
            - name: key1
              secret: $KEY
      - identity: {}          # still able to READ old plaintext Secrets
YAML
echo "   written (mode $(stat -c %a "$CFG"))"
EOF

echo "2. Point kube-apiserver at it (static pod manifest; kubelet restarts the API server)"
docker exec -i "$NODE" sh -s <<'EOF'
set -e
M=/etc/kubernetes/manifests/kube-apiserver.yaml
if grep -q -- '--encryption-provider-config' "$M"; then echo "   flag already set"; exit 0; fi
# Backup OUTSIDE manifests/: kubelet runs every file in that folder as a static pod.
cp "$M" /root/kube-apiserver.yaml.bak
sed -i 's|^    - --enable-bootstrap-token-auth=true$|&\n    - --encryption-provider-config=/etc/kubernetes/pki/encryption/config.yaml|' "$M"
grep -q -- '--encryption-provider-config' "$M" && echo "   flag added (backup: /root/kube-apiserver.yaml.bak)"
EOF

echo "3. Waiting for the API server to come back..."
sleep 10
until kubectl get --raw /readyz >/dev/null 2>&1; do sleep 3; done
echo "   API server ready"

echo "4. Rewrite every Secret so existing ones get encrypted too"
kubectl get secrets -A -o json | kubectl replace -f - >/dev/null
echo "   done"
