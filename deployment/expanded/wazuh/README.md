# Wazuh historical stack (pinned 4.9.2)

This directory holds the reviewed, version-pinned overlay for the Wazuh
single-node historical stack used by the exercise. It is **not** the upstream
tree: the official `wazuh/wazuh-docker` single-node deployment at the pinned
commit must be vendored beside it and its image identities recorded in
`manifest.json` before the stack is event-ready.

Status: **PENDING upstream vendoring; LIVE ACCEPTANCE BLOCKED** (no Docker/Linux
host in the wave-1/2 lane and no network to fetch upstream). No digest is
invented; `ridge.wazuh_provision.validate_manifest(..., require_digests=True)`
fails closed until every digest is a real immutable identity.

## Contents

- `manifest.json` — source commit, image tags and required digests.
- `index-template.json` — `silent-ridge-*` template with `timestamp` date mapping.
- `saved-objects.json` — a timestamped view and a timeless view. Coverage and
  catalog facts carry no timestamp, so the timeless view deliberately has no
  time field; a date filter must not hide them.
- `roles.json` — writer restricted to `silent-ridge-*`; participant read-only.
- `compose.wazuh.yaml` — pinned stack; indexer/manager stay on an internal
  network, only the dashboard is exposed, log rotation and healthchecks set.
- `generate-certs.sh` — idempotent local CA/node certificate generation.

## Bootstrap

```text
./generate-certs.sh /private/silent-ridge/certs
python -m ridge.wazuh_provision   # apply roles, views, index template and preflight
```

Apply the plan through the local-CA HTTPS client (`ca_context`) with the writer
credential restricted to the event index. Do not disable TLS verification and do
not assume Elasticsearch/OpenSearch API interchangeability.
