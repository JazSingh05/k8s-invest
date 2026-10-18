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

## The app: newsletter-signal portfolio tracker (always running locally)
**Goal:** Track a paid newsletter author's model portfolio (Google Sheet + weekly/mid-week emails) alongside MY real positions, and alert me on my phone — especially WHEN TO EXIT his non-long-term ("Trend") picks. Long-term ("Infinity") picks are set-and-forget.

**Design principles (decided 2026-10-18):**
- **Rules decide, Claude reads.** Alerts come from deterministic rules on his data (trend stop, valuation zones, timely-buy flags, his trims). Claude (Haiku) only extracts structure from emails and writes summaries. Claude does not give investment advice.
- **Alerts only.** No brokerage API, no trade execution, no brokerage credentials anywhere.
- **Licensed data stays private.** His sheet/picks/emails live only in local Postgres. Never in the public repo, never in test fixtures (use fake tickers/numbers), never screenshots.
- **Data path:** his sheet → my own Google Sheet (IMPORTRANGE or manual copy) → app reads MY sheet via Sheets API (read-only service account, shared on that one sheet only) → poll + diff snapshots → change events. Never scrape his sheet or seekingalpha.com.
- **Notifications:** Telegram bot or ntfy (not SMS).

**Key fields from his sheet:** ticker, timeframe (Trend/Infinity), priority, top long-term pick, timely buy now, his avg entry, trend stop, fair value, cheap, deeply undervalued, too expensive, update date.

| Service | Job | k8s concepts it teaches |
|---|---|---|
| sheet-sync | Poll my Google Sheet, snapshot + diff → change events ("stop raised 5→6", "new Timely Buy", "ticker removed") | CronJob, Secrets (SA key), egress to Google only |
| market-data | Daily closing prices after market close | CronJob, Secrets, egress NetworkPolicy |
| rules | My positions × his signals → alerts (close < trend stop, zone crossings, his changes) | Deployment, Redis queue consumer |
| notifier | Send alerts to Telegram/ntfy | Worker, egress to one domain |
| ingest (v2) | Parse his emails with Claude Haiku → structured updates | CronJob, Secrets, egress to 2 domains |
| portfolio-api | My positions, his picks, alert history | Deployment, Service, probes, HPA |
| frontend | Dashboard | Ingress, TLS |
| Postgres | Positions, snapshots, alerts | StatefulSet + PVC |
| Redis | Queue between sheet-sync/market-data and rules | KEDA scaling on queue depth |

**v1 (smallest useful thing):** picks + my positions loaded from a file → daily price CronJob → rule "close < trend stop on a Trend pick I own" → one Telegram/ntfy message.
**Open:** how his updates arrive (email? to Gmail?) — known after subscribing.

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
- Repo is PUBLIC (github.com/JazSingh05/k8s-invest): code only — no newsletter data, no real positions.

## Current status
Step 1 DONE (2026-10-18). App idea revised + agreed (see app section). NEXT: roadmap step 2 — portfolio-api by hand with kubectl.
