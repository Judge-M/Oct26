# N1 live acceptance receipt — 2026-09-18 (sanitized)

Revision: main `f4ad28b` plus four source fixes (below). Host: Windows workstation,
Docker Desktop engine 29.8.0 linux/x86_64. All credentials are generated disposable
values held privately under `work/n1-run/secrets/` (gitignored); none appear here.

## What ran live, in order

1. **Builds** — `python -m ridge.deploy build` × 4 + `verify-build`: iris, ctfd,
   integration, desktop. Receipts in `work/build-receipts/`.
2. **Desktop smoke** — `bash tests/desktop_container_smoke.sh`: PASS (offline Xfce,
   seeded WS17 case, tools execute, TSK libraries resolve, restart preserves work).
3. **Private runtime** — generated once and preserved on retry: two-team validated
   production profile (roster materialized by `ridge.deploy.config`), DB/app secrets,
   bridge secrets, Wazuh writer/reader/admin credentials.
4. **Central stack** — `compose.central.yaml` up: iris, iris-worker, iris-db
   (pgcrypto init via `iris-db-init` — worked as encoded), rabbitmq, ctfd, ctfd-db,
   ctfd-cache — all healthy on loopback.
5. **IRIS bootstrap (live)** — `flask silent-ridge-bootstrap` inside the container:
   case id **2**, open/closed status ids **1/4** (discovered from live `task_status`,
   never assumed), service user **2**, team users **3/4**. Preflight `ready: true`.
   **Repeat run: byte-identical inventory, no duplicates, passwords untouched.**
   Participant `team-01` login verified → 302 dashboard.
6. **CTFd provisioning (live)** — `flask silent-ridge-provision`: team ids **1/2**,
   six member users, team mode, registration closed, `ready: true`.
   **Repeat run: identical inventory.** Member `team-01-p01` login verified.
   Both apps' `/silent-ridge` endpoints correctly reject unauthenticated calls (401).
7. **Wazuh (live)** — upstream `wazuh-docker` vendored at v4.9.2 (commit `574c7b05`),
   images digest-pinned in `manifest.json` (`require_digests=True` now passes), local
   CA + node certs via `generate-certs.sh`, stack up (indexer healthy, dashboard
   serving on 8443). Then, from the integration image on the backend network:
   - admin applied index template, writer/reader roles, rolemappings, internal users (7 requests)
   - **writer** bulk-indexed 508 telemetry lines (505 unique; 3 exact duplicates share
     stable IDs) through the real `ridge.evidence_release.index` path; repeat indexing
     created zero duplicates
   - **reader** passed fact preflight: `data.session:S-41`, `data.host:WS-31`,
     `data.host:WS-22`, `data.type:coverage` — real incident rows returned
   - confinement proven: reader write → 403; writer on non-`silent-ridge-*` index → 403
   - saved views `silent-ridge-timed` / `silent-ridge-timeless` installed via dashboard API
   - final clean count: 505 documents

## Source defects found and fixed (in this PR branch)

1. **Python 3.9 runtime break in the IRIS image** — PEP 604 unions (`dict[...] | None`)
   in six `ridge/` modules killed the IRIS worker *silently* (gunicorn "Worker failed
   to boot", no traceback). Fix: `from __future__ import annotations`. Files:
   `ridge/ctfd_provision.py`, `ridge/deploy/providers.py`, `ridge/desktop_delivery.py`,
   `ridge/iris_bootstrap.py`, `ridge/state.py`, `ridge/wazuh_provision.py`.
2. **CTFd healthcheck used `curl`** — absent from `ctfd/ctfd:3.7.7`; also `/` 404s after
   setup. Fixed to `python -c urllib.request` against `/login`.
3. **Wazuh compose mounted config dirs at wrong targets** — upstream 4.9.2 mounts
   individual files (`opensearch.yml`, `internal_users.yml`, dashboard yml); rewritten
   to match, and the indexer gained a loopback-only host port for controller access.
4. **Wazuh writer role could not write** — OpenSearch 2.13 security also checks
   shard-level `indices:data/write/bulk[s]`; added `indices:data/write/bulk*` to
   `WRITER_ACTIONS` and regenerated the vendored `roles.json`.
5. **CTFd provision CLI crashed on old click** — `path_type=Path` ignored, bytes
   returned; now tolerates both.
6. **Stale "LIVE VALIDATION BLOCKED" headers** in `ridge/wazuh_provision.py` and
   `integrations/iris_bootstrap.py` updated to record live validation.

## Test evidence

`python -m unittest discover -s tests` → **221 tests, OK** after all fixes.

## Honest limits (what N1 did NOT prove)

- Host port publishing for the Wazuh indexer (127.0.0.1:9200) never came up under
  Docker Desktop despite a correct binding; all provisioning ran in-network, which
  matches the design ("reachable only through the local service network"). The
  loopback publish is kept in compose for the controller host but unproven here.
- No Guacamole session, no desktop attached, no claim/answer/point round-trip
  through the integration service (that's N2/N3). The integration service itself
  was used as the provisioning vehicle but has not run its long-lived worker role.
- Two teams only; ten-team capacity unmeasured. Event remains unstarted.
- Wazuh manager container runs but its API enrollment was not exercised (not needed
  for the historical-telemetry path).

## Next unblocked task

N2 — one real desktop through Guacamole with the seeded WS17 case, then evidence
delivery to desktops.
