#!/usr/bin/env bash
# Mirror a third-party image into our GHCR so the cluster only pulls from ghcr.io/jazsingh05.
# Usage: scripts/mirror-image.sh <source-image@sha256:...> <name:tag>
#   e.g. scripts/mirror-image.sh docker.io/library/postgres@sha256:266d... postgres:17-alpine
# Pulls the arm64 image BY DIGEST (exactly what we reviewed), re-tags it under
# ghcr.io/jazsingh05/kind/, pushes, and prints the digest to pin in manifests.
# Needs `docker login ghcr.io` with write:packages (laptop credential, not the cluster's).
set -euo pipefail
SRC="${1:?source image with @sha256 digest}"
DEST="ghcr.io/jazsingh05/kind/${2:?name:tag}"
[[ "$SRC" == *@sha256:* ]] || { echo "source must be pinned by digest" >&2; exit 1; }

docker pull --platform linux/arm64 "$SRC"
docker tag "$SRC" "$DEST"
# The digest the REGISTRY now has is the last sha256 the push prints. (Local RepoDigests
# can still show the source's multi-arch index digest, which isn't what we pushed.)
DIGEST=$(docker push "$DEST" | grep -oE 'sha256:[a-f0-9]{64}' | tail -1)
echo "Pin this in the manifest:"
echo "${DEST%%:*}@${DIGEST}"
