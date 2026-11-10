# Read ONLY the GHCR pull token. For namespaces that just need to pull our private
# images (cert-manager), not the app's other secrets (e.g. Postgres passwords).
path "secret/data/invest/ghcr-pull" {
  capabilities = ["read"]
}
