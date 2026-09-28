# Wazuh historical stack (pinned 4.9.2)

This directory holds the reviewed, version-pinned overlay for the Wazuh
single-node historical stack used by the exercise. It is **not** the upstream
tree: the official `wazuh/wazuh-docker` single-node deployment at the pinned
commit must be vendored beside it and its image identities recorded in
`manifest.json` before the stack is event-ready.

Status: the upstream 4.9.2 single-node stack is vendored and digest-pinned in
`manifest.json`. The API and offline configuration changes require acceptance
from a rebuilt air-gapped kit on the event host before this release is ready.

## Contents

- `manifest.json` — source commit, image tags and required digests.
- `index-template.json` — `silent-ridge-*` template with `timestamp` date mapping.
- `saved-objects.json` — a timestamped view and a timeless view. Coverage and
  catalog facts carry no timestamp, so the timeless view deliberately has no
  time field; a date filter must not hide them.
- `roles.json` — writer restricted to `silent-ridge-*`; participant data read
  limited to that pattern, with read-only Dashboard saved-object and global
  tenant access. Never map a participant to the `kibana_server` service role.
- `compose.wazuh.yaml` — pinned stack; indexer/manager stay on an internal
  network, only the dashboard is exposed, log rotation and healthchecks set.
- `api.yaml` — CA-signed API TLS with privilege dropping retained. The image
  copies this and its certificate into a writable path at first boot.
- `generate-certs.sh` — idempotent local CA/node certificate generation.
- `filebeat-init.sh` — runs inside the pinned manager after it seeds its own
  Filebeat files. It configures the certificate-matching `wazuh-indexer` host,
  preserves the image's template, and loads the generated indexer credential
  from a Docker secret into Filebeat's keystore on every container creation.

## Bootstrap

```text
./generate-certs.sh /private/silent-ridge/certs
python -m ridge.wazuh_provision   # apply roles, views, index template and preflight
```

Apply the plan through the local-CA HTTPS client (`ca_context`) with the writer
credential restricted to the event index. Do not disable TLS verification and do
not assume Elasticsearch/OpenSearch API interchangeability.

`ridge.deploy up` generates a separate Wazuh API password in the private
runtime, configures both manager and dashboard from it, and renders an
`ossec.conf` with `<update_check>no</update_check>` for offline use. Existing
runtime secrets are preserved. A missing API secret after initialization stops
readiness; restore that runtime instead of resetting its credentials. The
manager healthcheck authenticates to the API using the local CA before the
infrastructure stage verifies. Do not mount the stock `wazuh.yml` read-only:
the pinned dashboard image needs to write its API entry at startup.

The deployment also renders a private copy of `internal_users.yml` with a hash
of the generated indexer admin password. The plaintext remains only in the
private runtime secret, not in the vendored source or Filebeat config. This
must be done before the indexer initializes its security index. Replacing the
file after a security index exists is **not** a password rotation; the old
security state must be handled through the tested recovery/rotation procedure.
The evidence probe runs `filebeat test output` against the CA-verified indexer
so a healthy manager process alone does not claim an ingest-ready event.
