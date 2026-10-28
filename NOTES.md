# NOTES — K8s learning log

## Session 1 — 2026-10-16
- Machine is bare: no Xcode Command Line Tools, no Homebrew, no git.
- Plan: CLT → Homebrew → Colima + docker CLI → kind, kubectl, k9s, helm.
- Installed Xcode CLT (GUI installer stalled; Homebrew installer would also have handled it).
- Installed Homebrew 7.0.9 → /opt/homebrew, PATH set in ~/.zprofile via `brew shellenv`.
- Security note: Homebrew install is `curl | bash` with sudo — trust-by-origin, not verification.
- brew installed: colima 0.10.3, docker CLI 29.9.1, kind 0.33.0, kubectl 1.37.1, k9s 0.51.0, helm 4.3.1 (+lima). Terraform deferred to EKS phase.
- Colima VM up: Ubuntu 24.04 aarch64, vz + virtiofs, 8 CPU / 24GiB. docker CLI → context 'colima' → ~/.colima/default/docker.sock
- Tag vs digest: tags are mutable pointers, digests are content hashes → why Kyverno bans :latest and cosign signs digests.
- Moved project to ~/code/k8s-invest.
- kind cluster 'invest' up: k8s v1.37.0, 1 control-plane + 2 workers, nodes = Docker containers (kindest/node), Debian 13, containerd 2.3.4. Context: kind-invest.
- Workers briefly NotReady right after joining: kubelet waits for CNI (kindnet) to configure pod networking.
- docker ps: apiserver port 6443 in control-plane container → forwarded to 127.0.0.1:<random> on the Mac (localhost-only = not exposed to the LAN).
- Node OS-IMAGE is Debian (kindest/node) but KERNEL is the Colima VM's Ubuntu kernel → containers bring a filesystem, never a kernel.
- kubeconfig = clusters (where + CA to trust server) + users (client cert/key) + contexts (cluster+user pair). Auth is mTLS; k8s has no user DB — identity = cert CN (user) / O (groups).

### Paused here (end of session 1)
Next up: run `kubectl auth whoami` + decode the client cert (look for O=system:masters, notAfter) → answer "how would you revoke it?" → then kube-system tour + DaemonSets.
Resume: `colima start` (remembers its config), then `kubectl get nodes`.

## 2026-10-17
- Singh changed the project idea a bit → pause before any app code (step 2) and get the new idea first. Flagged in CLAUDE.md.
- Cluster survives `colima stop/start`: Docker restart policy brings node containers back; state lives on a Docker volume at /var (etcd = /var/lib/etcd). Control plane = static pods kubelet starts from /etc/kubernetes/manifests.
- Layers: nodes (kind/EC2, not k8s YAML) → control plane (kubeadm static pods) → add-ons (CoreDNS Deployment, kube-proxy + kindnet DaemonSets) → our apps (step 2+).
- Deployment = N replicas anywhere (scheduler picks). DaemonSet = exactly 1 per (matching) node. Security agents/CNI/log shippers are DaemonSets — and usually the most privileged pods.
- kube-proxy uses hostNetwork → pod IP = node IP. Node IPs reshuffled after restart → never hard-code IPs.
- Broke it: deleted kube-proxy pod → DaemonSet controller recreated it on the SAME node within seconds, new name, RESTARTS 0. Reconciliation loop: desired vs actual.
- CORRECTION: my kubeconfig cert is NOT system:masters. User=kubernetes-admin, group=kubeadm:cluster-admins → bound to ClusterRole cluster-admin via a normal ClusterRoleBinding (revocable by deleting the binding). system:masters = break-glass only, in /etc/kubernetes/super-admin.conf on the control plane; it bypasses RBAC entirely.
- Decoded cert: O=kubeadm:cluster-admins, CN=kubernetes-admin, issuer CN=kubernetes (cluster CA), valid 1 year. K8s has no cert revocation (no CRL/OCSP) → remove RBAC binding, wait for expiry, or rotate CA. EKS uses short-lived IAM tokens instead.
- k9s: [RW] = read-write (use `k9s --readonly` on prod contexts). CPU/MEM n/a = no metrics-server (needed for `kubectl top` + HPA, step 6).
- Pod Events show the lifecycle + WHO did each step: default-scheduler (Scheduled → picks node; DaemonSet pods go through the scheduler too, pinned via node affinity) → kubelet (Pulled → Created → Started).
- "image already present on machine" = imagePullPolicy IfNotPresent → cached image reused without re-checking the registry. Events are kept only ~1h by default → ship them somewhere for forensics.

### ✅ Roadmap step 1 complete (2026-10-18)
Next: STOP — get Singh's revised app idea before step 2.
- Repo: https://github.com/JazSingh05/k8s-invest (public). 3 secret-scanning layers: gitleaks pre-commit hook (local, opt-in, bypassable with --no-verify) → CI (step 8, enforced) → GitHub push protection (server-side).
- Git identity uses the GitHub noreply email so the real address isn't in public history. HTTPS + gh credential helper; token in macOS Keychain (broad `repo` scope — not least-privilege).
- NOTE: the pre-commit hook lives in .git/hooks/, which is NOT committed → a fresh clone has no hook. Reinstall after cloning.

## Session — 2026-10-19 → 10-21: trunk-based + step 2a
- Trunk-based: main protected by GitHub ruleset `protect-main` (PR required, no force push/delete, linear history), squash-only, branches auto-delete. Later Argo CD deploys main → protecting main = protecting prod.
- portfolio-api: rules in picks.py (pure functions) separate from web layer main.py (FastAPI) → rules testable without a server, reusable by the digest CronJob.
- Columns matched by header NAME, not position → real sheet can differ, only config changes.
- Dockerfile: 3 stages. deps (venv; requirements copied BEFORE code so code edits reuse the cached pip layer) → test (pytest; failing test = failed build) → runtime (clean base, only venv+app copied, USER 10001). Base pinned by digest.
- .dockerignore kept build context at 22KB (no .venv upload).
- `docker run` puts the container NEXT TO the kind nodes, not in the cluster. Each kind node has its own containerd image store → need `kind load docker-image` (or a registry) or pods hit ImagePullBackOff.
- Verified: /picks ranking matches tests; `id` → uid=10001; /docs disabled by default.
- Tooling: uv + Python 3.13 venv for VS Code/pytest locally; Docker CLI lacks buildx (legacy builder) → add before step 8.

## Session — 2026-10-21: step 2b (in progress)
- Namespace `invest` for the app (RBAC / NetworkPolicy / PSA boundary later).
- Bare Pod with short image name → kubelet expands to docker.io/library/... → ErrImagePull → ImagePullBackOff (backoff 10s→5m). Short names = supply-chain risk; use fully qualified registry names (GHCR, step 8).
- `kind load docker-image` copies the image into EACH node's containerd store (no registry). Pod recovered by itself on next retry — same pod object, no re-apply.
- port-forward goes through the API server (RBAC `pods/portforward` bypasses NetworkPolicy); tied to ONE pod; needs its own terminal tab.
- Deleted bare pod → stays gone (no controller). Deployment → ReplicaSet (pod-template-hash) → Pods. Deleted pod → ReplicaSet recreated it with a NEW name and NEW IP.
- `kubectl diff` = terraform plan. Showed server defaults: RollingUpdate 25%/25%, revisionHistoryLimit 10, IfNotPresent, empty securityContext + resources (fix in steps 6/9).
- `last-applied-configuration` annotation stores the whole applied file → Secrets applied client-side get a 2nd copy in the annotation → use server-side apply for Secrets.
- Scaling changes replicas on the SAME ReplicaSet. Control plane tainted NoSchedule → app pods never land there (protects etcd/CA). Scale-down deletes: unready first → keep spread → newer (bucketed) first.

## Session — 2026-10-23: Service
- Pods survived `colima stop/start` (same names, RESTARTS 1) but got NEW IPs (10.244.2.3/1.4 → 1.2/2.2). Loaded image survived too (containerd store on /var volume).
- Service `portfolio-api` (ClusterIP 10.96.84.149, port 80 → targetPort 8000). Selects pods by label, not name/IP. EndpointSlice = live list of pod IPs.
- Saw kube-proxy's iptables rules on a node: KUBE-SERVICES (match ClusterIP) → KUBE-SVC (random, probability 0.5) → KUBE-SEP (DNAT to pod IP:8000). Routing happens in the caller node's kernel; kube-proxy only writes rules.
- Service IPs (10.96.x) and pod IPs (10.244.x) are separate ranges. ClusterIP = routing, not access control → NetworkPolicies in step 5.
- In-cluster test: `kubectl run tmp --rm -it ... curlimages/curl` → by name `http://portfolio-api`. Fast commands race the attach (output lost) → add `sleep 2` or read `kubectl logs`. Interactive sessions are recorded in container logs → never paste secrets.
- Broke it: scaled to 0 (imperative `kubectl scale`) → Service + ClusterIP unchanged, EndpointSlice empty → curl fails INSTANTLY (exit 7, 1 ms): kube-proxy installs REJECT for endpoint-less Services. Exit 6 would mean DNS failed (no Service).
- Drift: live replicas 0 vs git 2; `last-applied-configuration` still said 2 (only `apply` writes it). `kubectl diff` showed it; `kubectl apply` restored it; empty diff afterwards = in sync. GitOps (Argo CD) automates exactly this.
- Pods came back with new IPs again (10.244.1.8, 2.3); Service didn't care.

### ✅ Roadmap step 2 complete (2026-10-24)

## Session — 2026-10-24: GHCR (private) prep
- Decided: push portfolio-api to GHCR as a PRIVATE package → cluster pulls with an imagePullSecret (dedicated read-only `read:packages` token, expiring) — not the broad gh token.
- `docker login` without a helper stores base64 `user:token` in ~/.docker/config.json (plain text). Installed `docker-credential-helper` → `"credsStore": "osxkeychain"` → token goes to macOS Keychain. Backup: ~/.docker/config.json.bak.

- Pushed `ghcr.io/jazsingh05/portfolio-api:0.1.1` (private, linked to repo via `org.opencontainers.image.source` LABEL). `gh auth refresh -s write:packages` = publisher cred, stays on laptop. config.json shows `"ghcr.io": {}` → token in Keychain, not on disk.
- Layer cache is a chain: changing step N rebuilds N+1…end → put rarely-changing, slow steps (base, deps) early.
- Colima uses containerd image store → local image ID == registry manifest digest.
- Image ref `name:tag@sha256:…` → digest wins; tag is just a human label.

## Session — 2026-10-25: rollout stuck on 401 → Vault for ESO
- Applied GHCR Deployment → new ReplicaSet `777dfff9fb`, pod ImagePullBackOff (401 from `ghcr.io/token?scope=repository:…:pull` = registry v2 token flow, anonymous). Old RS kept 2/2 serving: maxSurge 25%→1, maxUnavailable 25%→0, so it waits for the new pod to be Ready. No readiness probe yet → "Ready" only means "started" (step 6).
- generation bumps on every spec change; template change → new hash → new RS; old RS holds the old template (rollback).
- Labels are routing, not identity: anyone who can create pods in `invest` can label one `app: portfolio-api` and receive Service traffic.
- Every pod auto-mounts a SA token (`kube-api-access-*`, ~1h, rotated) → `automountServiceAccountToken: false` later. QoS BestEffort = first evicted.
- zsh: single-quote args with `[ ]`, `?`, `*` (jsonpath/custom-columns).
- Decided: pull secret comes from Vault via External Secrets Operator (not created by hand).
- Vault: Helm chart 0.34.1 (`k8s/vault/values.yaml`), standalone, injector off. Chart pulled for reading into gitignored `charts-vendor/` (+ `vault-rendered.yaml` via `helm template`).
- StatefulSet = stable names (vault-0) + PVC per pod from volumeClaimTemplates (`data-vault-0` = template-sts-ordinal). Headless Service (`ClusterIP None`) = per-pod DNS.
- PVC/PV/StorageClass: claim = request, PV = actual storage, SC = recipe. `WaitForFirstConsumer` → scheduler picks the node first (`volume.kubernetes.io/selected-node` annotation), then local-path makes a 0777 folder on that node → PV node affinity pins vault-0 to invest-worker2 forever.
- Vault init (1 share / threshold 1) → unseal key + root token straight into macOS Keychain (`kind-invest-vault-unseal`, `kind-invest-vault-root`), never printed. Vault stores neither (only a hash of the token); lose the unseal key = data gone. Readiness probe = "unsealed?".
- Gotcha: `vault operator unseal -` does NOT read stdin. `vault write sys/unseal key=-` does.
- Vault binds `system:auth-delegator` (TokenReview) → basis of the Kubernetes auth method. Listener TLS off (fine locally, finding in prod). Prod: auto-unseal with KMS.

## Session — 2026-10-25 (late): Vault identity for invest
- Same Vault `cluster_id` after 3 VM restarts → PVC kept the data; unseal needed each start.
- KV v2 at `secret/`; pull token at `secret/invest/ghcr-pull` (username + token). Real API path = `secret/data/invest/...` (policies use it).
- Root token passed into the pod over stdin (`sh -c 'read -r VAULT_TOKEN; ...'`), never argv/screen. Vault config as code: `k8s/vault/configure.sh` + `policies/invest-read.hcl`.
- Identity: SA `invest/eso-vault` (no pods, automount off) → Vault role `invest-eso` (bound SA name+namespace, `audience=vault`, policy invest-read, 15m). Dedicated per-namespace SA, not ESO's own → tenant boundary = namespace.
- JWT = header.payload.signature; payload readable, signature by API server's sa.key; bearer token. Claims: aud, iss, sub, exp/iat/nbf, jti, SA uid (delete+recreate SA = revoke its tokens).
- Tested by hand: login → read invest/ghcr-pull ✓, other path 403, write 403, token without aud=vault → 403 invalid audience (replay blocked).
- ESO chart 2.14.0 pulled to charts-vendor/: 25 CRDs + controller + webhook (admission) + cert-controller. Controller ClusterRole = all Secrets everywhere + mint any SA token → its namespace is a crown jewel.

## Session — 2026-10-26: TLS/CA + ESO → rollout finished
- TLS: key pair → cert = CA-signed "this public key belongs to <name>" (like a JWT for keys). Verify = signature + dates + SAN matches what you dialed + proof of private key. CA cert is self-signed trust anchor.
- kind PKI (/etc/kubernetes/pki): cluster CA, separate etcd CA, front-proxy CA; sa.key = JWT signer (not a CA). API server is a server to us, a client to kubelet + etcd (all mTLS). apiserver.crt SANs incl 10.96.0.1, 127.0.0.1; 1y leaf (kind re-issued it when node IP changed), notBefore backdated 5m; CA 10y.
- Same CA in 3 places: node pki (kubeadm init) → ConfigMap kube-root-ca.crt in every namespace (controller-manager root-ca-cert-publisher) → projected into every pod (token + ca.crt + namespace); kubeconfig (kind copied admin.conf, server rewritten to 127.0.0.1:49404).
- `openssl s_client` without CA → verify code 21; that's what `-k`/insecureSkipTLSVerify accept. ca.key = crown jewel; certs can't be revoked.
- etcd = cluster's key-value DB at /registry/<resource>/<ns>/<name>; only the API server talks to it (mTLS via etcd CA). etcdctl via healthcheck-client cert.
- Namespaces now owned by YAML (k8s/vault/namespace.yaml, k8s/external-secrets/namespace.yaml), not `--create-namespace` → can carry PSA labels later.
- Helm vs kubectl: our app = plain YAML (learning); third-party = Helm (34k lines for ESO; release tracking, upgrades prune, rollback). Chart ≈ Terraform module. Our own chart in step 7. `helm install --dry-run=server` = validate without changes; helm-diff plugin later.
- ESO 2.14.0 installed: 25 CRDs (CRD = noun, controller = verb), controller + webhook (failurePolicy Fail = fail-closed) + cert-controller. Upstream ships restricted securityContext.
- SecretStore `vault` (namespaced, serviceAccountRef eso-vault, audiences [vault]) → Valid in 3s. Client names the role; Vault decides policy. No SA token Secret exists (TokenRequest).
- ExternalSecret `ghcr-pull`: fetch username+token → template into kubernetes.io/dockerconfigjson (kubelet requires Docker's config.json format) → Secret owned by the ExternalSecret, refresh 1m.
- Stuck pod recovered on its next backoff retry → rollout finished: 777dfff9fb 2/2 (GHCR digest), 666c8f6695 scaled to 0. Second node pull: "already present on machine" (per-node image cache).

## Session — 2026-10-27: break-it on the secrets pipeline + rollback
- Vault sealed after colima start → SecretStore InvalidProviderConfig, ExternalSecret SecretSyncedError, Secret kept, app fine. After unseal ESO stayed broken: exponential backoff (~16m cap). Nudge = `kubectl annotate … force-sync=$(date +%s) --overwrite` (watch event → immediate reconcile); prod: `kubectl rollout restart deploy/external-secrets` resets all queues. Each object has its own backoff.
- Rotation: new PAT → `vault kv put` (KV v2 version 2) → ESO rewrote Secret within 1m (data-hash annotation; same data = no write) → cordon + `crictl rmi` + delete pod forced a real pull on a cache-less node → old PAT revoked. Running containers don't need their image (snapshot).
- Deleted Secret ghcr-pull → ESO recreated it the same second (watches owned Secrets).
- ESO webhook scaled to 0 → writes to ExternalSecret rejected (failurePolicy Fail, "connection refused" to webhook Service); status/sync kept working.
- etcdctl read /registry/secrets/invest/ghcr-pull → token in plaintext. Wrote `scripts/enable-etcd-encryption.sh` (secretbox, key generated on node, NOT run yet). EKS: envelope encryption with customer-managed KMS key. Encryption at rest ≠ access control: RBAC get/list secrets still reads decrypted.
- RBAC hardening added to roadmap step 9 (CLAUDE.md).
- Rollback: `rollout undo` → old RS scaled up as revision 3; last-applied annotation untouched → drift vs git; `kubectl apply` → revision 4, no diff, /healthz ok.
- New: docs/kooper-teddies-notes.md (study guide with Mermaid diagrams), updated each PR.
### Paused here
PR for feat/ghcr-private open. Every `colima start`: unseal Vault:
`security find-generic-password -a vault -s kind-invest-vault-unseal -w | tr -d '\n' | kubectl exec -i -n vault vault-0 -- vault write sys/unseal key=-`
Optional: run scripts/enable-etcd-encryption.sh and verify `k8s:enc:secretbox` prefix in etcd.
Next: roadmap step 3 — Postgres StatefulSet + PVC, ConfigMaps (header map), Secrets via ESO.
