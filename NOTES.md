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
