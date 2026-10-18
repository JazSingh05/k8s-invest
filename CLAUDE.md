# CLAUDE.md — K8s Learning Project

## Who I am
Singh, cloud security engineer (access management, service-to-service security, secrets management, secure dev workflows). Strong on cloud security, **new to Kubernetes** — I don't know basics like what a DaemonSet is yet.

## The real goal
Learn Kubernetes (and later AWS networking) deeply. The app is an excuse to touch every k8s concept. **Teaching beats speed.**

## How to work with me (most important section)
- **Teach piece by piece.** For every new component: what it is → why it exists → how it connects to what we've already built → then build it.
- **Explain commands before running them.** Tell me what a command does and what to expect. Let me run the important ones myself when it helps me learn.
- **Make it visible.** After each step, show me what to look at in k9s or kubectl so I can see the thing working.
- **Break things on purpose.** Once something works, have me kill/misconfigure it and watch k8s react.
- **One step at a time.** Don't jump ahead or build three components in one go. Check that I understand before moving on.
- Be blunt and direct. Skip excessive caveats. Give a clear recommendation, not a menu.
- Point out where security decisions matter — that's my field and my interview story.

## Machine
16" MacBook Pro, M5 Pro (18-core CPU), 64GB RAM, 2TB SSD. Apple Silicon (arm64) — all images are arm64.

## Phase: LOCAL ONLY (no AWS/EKS yet)
Budget: ~$0–5/month (only Claude API usage). Do not create any cloud resources.

## Tech stack
**Local platform**
- Colima (Docker runtime) — start with: `colima start --cpu 8 --memory 24 --disk 200 --vm-type vz`
- kind (multi-node local cluster), kubectl, k9s, Helm, Terraform
- Calico or Cilium as CNI — kind's default CNI does NOT enforce NetworkPolicies
- kubeadm once on VMs, later, to learn control-plane bootstrapping

**CI (GitHub Actions, public repo)**
- SAST: Semgrep or CodeQL · secrets: gitleaks · deps + images: Trivy
- arm64 image builds, cosign signing, syft SBOM, push to GHCR

**CD**
- `helm install` by hand first, then Argo CD (GitOps)
- Checkov / Trivy config on Terraform + Helm; kubescape for cluster posture

**Admission control**
- Kyverno: signed images only, no root, resource limits required, no `:latest`
- Pod Security Admission at `restricted`

## The app: fake-money investing app (always running locally)
| Service | Job | k8s concepts it teaches |
|---|---|---|
| market-data | Pulls prices on a schedule (Finnhub/Alpha Vantage free tier) | CronJob, Secrets, egress NetworkPolicy |
| research | Claude API (Haiku) analyzes prices/news → buy/sell signals | Workers, queues, egress to one domain |
| trader | Executes fake trades from signals | Service-to-service auth, mTLS later |
| portfolio-api | Holdings and P&L | Deployment, Service, probes, HPA |
| frontend | Dashboard | Ingress, TLS |
| Postgres | Portfolios + trades | StatefulSet + PVC |
| Redis | Queue between research and trader | KEDA scaling on queue depth |

## Roadmap (in order)
1. Tooling: Homebrew, Colima, kind, kubectl, k9s, Helm — tour a fresh cluster (nodes, pods, namespaces, DaemonSets)
2. Pods, Deployments, Services — deploy portfolio-api by hand with kubectl
3. Postgres StatefulSet + PVC, ConfigMaps, Secrets
4. Remaining services, Redis, CronJob
5. Ingress, NetworkPolicies (default deny), Calico/Cilium
6. Reliability: probes, PDBs, HPA, topology spread, resource requests/limits
7. Helm charts, then Argo CD
8. GHA CI with scanning, signing, SBOM
9. Kyverno + Pod Security Admission
10. Monitoring: Prometheus/Grafana (with PVCs)
11. Later: EKS phase (Terraform apply/destroy per session, Pod Identity, ALB + LB Controller, VPC CNI, RDS)

## Ground rules
- Never commit secrets. API keys go in k8s Secrets / local `.env` (gitignored).
- Ask before installing anything new on my machine.
- Keep a short `NOTES.md` log of what we learned each session.

## ⚠️ Project idea changed (2026-10-17)
Singh has revised the app idea. **Before writing any app/service code** (starting at roadmap step 2, portfolio-api), STOP and ask Singh for the updated idea. Do not assume the service table above is current.


## Current status
Step 1 DONE (2026-10-18): tooling, Colima, kind cluster "invest" (1 CP + 2 workers), kubeconfig/RBAC identity, DaemonSets + reconciliation, k9s. NEXT: get revised app idea from Singh before step 2 (see flag above).
