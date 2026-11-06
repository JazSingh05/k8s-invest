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

## Session — 2026-11-03: least-privilege Postgres applied
- Both passwords generated straight into Vault (`invest/postgres-admin` user pgadmin, `invest/postgres-app` user portfolio_app); old `invest/postgres` removed with `kv metadata delete` (plain `kv delete` = soft delete, restorable).
- "Factory reset": scale sts to 0 → delete PVC → PV + node folder gone (reclaim Delete). Needed because initdb scripts only run on an EMPTY data dir.
- Deleted ExternalSecret postgres-auth → its Secret went too (creationPolicy Owner → ownerReference → garbage collector).
- Applied externalsecrets + configmap + sts: new PVC, both ES SecretSynced, logs show 10-app-user.sh ran (CREATE ROLE … ALTER ROLE).
- ConfigMap = non-secret config outside the image (env vars or files). Secret = same shape, for sensitive values (hidden in describe, tighter RBAC). Never put passwords in a ConfigMap.
- `volumes:` (pod level) = what + where from (PVC / Secret / ConfigMap); `volumeMounts:` (container) = where it appears; linked by name. Secret volumes are tmpfs (RAM). In a StatefulSet the `data` volume is added automatically from volumeClaimTemplates.
- replicas = number of pods; `containers:` list = containers per pod (sidecars share IP + volumes). READY 1/1 = ready/total containers.
- Bug: probe `pg_isready -U pgadmin` without `-d` → FATAL "database pgadmin does not exist" every 5s in Postgres logs while the probe still PASSED. Fixed with `-d`. Lesson: green probe ≠ correct probe; read the app logs. Re-apply restarted postgres-0 with the same PVC; init did not re-run.
- 2026-11-05: verified. `\du`: pgadmin = Superuser/Create role/Create DB/Replication/Bypass RLS; portfolio_app = no attributes. `\dn`: schema portfolio owned by portfolio_app. Break-it as portfolio_app over TCP + password: CREATE TABLE in own schema OK; CREATE ROLE, ALTER ROLE … SUPERUSER, CREATE DATABASE, write to public, read pg_authid all DENIED. (Test table `portfolio.picks` left in place, empty.)
### Paused here
TODO Singh: delete unused GHCR package `mirror/postgres`.
Every `colima start`: unseal Vault:
`security find-generic-password -a vault -s kind-invest-vault-unseal -w | tr -d '\n' | kubectl exec -i -n vault vault-0 -- vault write sys/unseal key=-`
Next: mirror Vault + ESO (public) + helm upgrade → ConfigMap sheet header map → wire portfolio-api to Postgres as portfolio_app → notes doc → PR.
