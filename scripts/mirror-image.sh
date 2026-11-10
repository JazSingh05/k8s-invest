#!/usr/bin/env bash
# Mirror a third-party image into our GHCR so the cluster only pulls from ghcr.io/jazsingh05.
# Usage: scripts/mirror-image.sh <source-image@sha256:...> <name:tag>
#   e.g. scripts/mirror-image.sh quay.io/jetstack/cert-manager-controller@sha256:e396... cert-manager-controller:v1.21.3
#
# Registry-to-registry copy with crane (go-containerregistry): the bytes are copied as-is,
# never unpacked locally, so the mirror's digest IS the source digest. That means:
#   - verifying the mirror = comparing two equal digests
#   - upstream signatures (cosign) stay valid on our copy
#   - no dependency on the local Docker image store (its containerd snapshotter drops
#     shared layer blobs, which broke the old pull/tag/push approach)
# Pass the arm64 platform-manifest digest to copy one architecture, or the index digest
# to copy every architecture.
# Auth: crane reads ~/.docker/config.json (Keychain credential helper), so it uses the
# laptop's `docker login ghcr.io` (write:packages), not the cluster's read-only token.
# New GHCR packages are PRIVATE by default.
set -euo pipefail
SRC="${1:?source image with @sha256 digest}"
DEST="ghcr.io/jazsingh05/kind/${2:?name:tag}"
[[ "$SRC" == *@sha256:* ]] || { echo "source must be pinned by digest" >&2; exit 1; }
WANT="${SRC##*@}"

crane copy "$SRC" "$DEST"
GOT=$(crane digest "$DEST")
[[ "$GOT" == "$WANT" ]] || { echo "digest mismatch: source $WANT, mirror $GOT" >&2; exit 1; }
echo "Verified: mirror digest == source digest. Pin this in the manifest:"
echo "${DEST%%:*}@${GOT}"
