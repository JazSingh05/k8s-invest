# Read-only access to the invest namespace's secrets, nothing else.
# KV v2 API paths include /data/ (the CLI hides it): `vault kv get secret/invest/x`
# actually reads secret/data/invest/x.
path "secret/data/invest/*" {
  capabilities = ["read"]
}
