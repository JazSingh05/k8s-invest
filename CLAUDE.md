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
- **Notifications:** Telegram bot (private chat). Not SMS, not public ntfy topics.

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

**V1 scope (updated 2026-10-18) — ALL long-term picks, ranked, DAILY digest on Telegram:**
- Input: his model portfolio data (my copy of his sheet; manual import first, sheet-sync later).
- **Long-term pick** = Timeframe = "Infinity" OR "Top Long Term Pick" flag set (union). Tag each with which signal(s) it has. Edge case seen in sample: a pick can be Timeframe "Trend" AND flagged "Top Long Term Pick" — include it, mark it "Trend + Top LT" since his trend stop still applies.
- **Ranking:** Priority Ranking (higher first) → Top Long Term Pick flag → his Exposure % (higher first). Confirm Priority meaning after subscribing.
- **Two views, never blended into one score:** (1) *Conviction* = the ranking above (changes only when he edits). (2) *Valuation today* = which of HIS zones the price is in (changes daily). Shown side by side; no Claude-invented weighting.
- **Zone rule (his numbers only):** price ≤ Deeply Undervalued → Deeply undervalued; ≤ Cheap → Cheap; ≤ Fair Value → Below fair; < Too Expensive → Above fair; ≥ Too Expensive → Too expensive. Blank valuations (e.g. ETFs) → "n/a".
- **Distance** = (level − price) / price (verified against his sheet: positive = price below that level).
- **Stale flag:** valuation Update Date older than 60 days → "⚠️ stale".
- **Daily changes to report:** zone crossings, his edits to levels/priority/flags, picks added/removed.
- Ignored in V1: Trend Stop, Price to Stop, Portfolio Risk, Investment Return to Stop, Daily Change, Shares, his Return.
- **Daily CronJob** after US market close (~5:30pm ET) → Claude Haiku writes the digest: "what changed since yesterday" first, then the full ranked list with price vs HIS valuation levels (deeply undervalued / cheap / fair / too expensive).
- The digest reports HIS recommendations and numbers. No opinions or picks of its own.
- **Delivery: Telegram bot** (private chat; bot token in a k8s Secret). Not ntfy.sh — public topics would leak licensed data. No dollar amounts of MY positions in messages (bot chats aren't E2E encrypted).
- CronJob uses `startingDeadlineSeconds` so a run missed while the laptop sleeps runs on wake; job is idempotent (based on latest data, safe to re-run).
- V1 services: portfolio-api (step 2), Postgres (step 3), daily-digest CronJob + Telegram notifier (step 4). Current price comes from his sheet → no market-data service yet.
- **Later:** web dashboard in-cluster (step 5, Ingress + TLS) with history, linked from each message; phone access via Tailscale, never exposed to the internet. No native app.
- Deferred to V2+: Trend picks, my positions, exit/stop alerts, email ingest, rules engine, Redis.
**Build-first plan (decided 2026-10-19):** build the whole V1 now against a FAKE sheet with the same columns as his (fake tickers/numbers), then subscribe and plug in. Plug-and-play = sheet ID + header→field mapping live in a ConfigMap; columns matched by HEADER NAME, not position, so layout differences only need a config change.
**Service facts (checkout page, 2026-10-19):** $599/yr; annual plan cancellable in first month for refund of remaining 11 months. Includes Long-Term Growth Portfolio (our V1 target), PowerFactors Microcaps, options/ETF strategies, weekly macro, chatroom with live trade alerts, valuation spreadsheet.
**Open (after subscribing):** do trade alerts also arrive by email or only in chat; meaning of Priority Ranking (is 3 best?); meaning of purple-colored valuation numbers; real sheet layout (tabs, merged headers, hidden rows); whether sheet or alerts update first.

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
Steps 1–2 DONE (2026-10-24): cluster tour; portfolio-api (FastAPI, fake data) running as Deployment (2 replicas) + ClusterIP Service in namespace `invest`; image loaded with `kind load` (no registry yet). Trunk-based: main protected, PRs + squash merges. NEXT: optional manual GHCR push, then step 3 (Postgres StatefulSet + PVC, ConfigMaps, Secrets). Still waiting on Singh's subscription for real data.
