# N4 Receipt — One-Command Local Lifecycle (`ridge/deploy`, cards E01/E02)

Date: 2026-09-19. Branch: `feat/n4-local-lifecycle`. Base: `main` after N3 merge (PR #28).
Test count: **240 passing** (was 221 after N3; +12 lifecycle, +7 launcher statics).

## What was built

- **`ridge/deploy/local.py`** (~1100 lines) — `LocalStack`, a stage-by-stage local
  lifecycle orchestrator over one runtime directory:
  `ARTIFACTS_VERIFIED → INFRASTRUCTURE_READY → APPLICATIONS_READY → IDENTITIES_READY
  → DESKTOPS_READY → EVIDENCE_READY → PROVISIONED_PAUSED`.
  Entry points: `up`, `start`, `pause`, `status`, `down`, `backup`;
  `restore`/`switch` fail closed with explicit N5 deferral messages.
  Every stage is probe-first and journal-backed (`deploy-journal.sqlite`):
  - repeated `up` re-probes verified stages; a probe failure after verification is an
    actionable error and **never** silently recreates state;
  - after an intentional `down` (journal `STOPPED`), `up` re-applies and re-verifies
    each stage (`journal.reopen_step`) — kill/resume works at any phase;
  - `start` refuses unless journal is `PROVISIONED_PAUSED`, every step verified, and a
    **real controller preflight** passes; only then `mode → running`;
  - `pause` is truthful (reports previous mode), `status` is structured JSON with
    `event_ready` and per-stage probe errors, `backup` requires paused + drained
    outbox and writes SQLite state, journal, config, inventories and
    `SHA256SUMS.json` under `backups/<UTC stamp>/`.
- **`ridge/deploy/indexer_job.py`** — evidence provisioning job that runs **inside the
  integration image on the Wazuh backend network** (see defect 8 below).
- **`ridge/deploy/__main__.py`** — CLI wiring; lifecycle actions require
  `--profile`/`--runtime`; bare lifecycle commands error with "no event or resources
  were changed"; `_release_fingerprint` derives the shared source fingerprint from the
  four build receipts (all must agree).
- **`ridge/deploy/journal.py`** — added `reopen_step(name)` (verified → started for
  STOPPED-resume).
- **`ridge.ps1`** (repo root, card E02) — Windows launcher: prereq check, image cache
  check, `prepare` verified live on this host (exit 0). `prepare` on a clean host and
  full clean-host e2e remain untested (see Limitations).
- **`tests/test_deploy_lifecycle.py`** (12 tests) + **`tests/test_ps1_launcher.py`**
  (7 tests): scripted FakeRunner/FakeHost covering repeated `up`, kill/resume,
  re-probe failures, pause/start gating, secrets-never-regenerated, backup.

## Live verification (adopted N1/N3 stack, profile `work/n4-run/profile.json`)

Commands run with `python -m ridge.deploy <action> --profile work/n4-run/profile.json
--runtime work/n4-run`:

1. `up` → all 7 stages verified → `PROVISIONED_PAUSED` (index `silent-ridge-oct26`,
   511 documents; real controller preflight `ready: true`, 2 teams, 20 tickets).
   Identity bootstrap repeated **byte-identical** against adopted N1 inventories
   (refusal path for changed inventories also unit-tested).
2. Second `up` → idempotent, probe-only, same result.
3. `status` → `event_ready: true`, exercise `ok`, mode `paused`, `pending: 0`.
4. `start` → `{"state": "RUNNING", "mode": "running"}`, confirmed in `state.sqlite`.
5. `pause` → `{"previous": "running", "mode": "paused", "state": "PROVISIONED_PAUSED"}`.
6. `backup` → `work/n4-run/backups/20260919T232648Z`, 6 files + SHA256SUMS.
7. `down` → 0 running containers, volumes kept, journal `STOPPED`.
8. `up` (resume) → every stage re-applied and re-verified → `PROVISIONED_PAUSED`;
   mode still `paused`; **no state rewritten** (adopted config/state untouched).
9. `restore` / `switch` → refused with explicit N5 deferral; "No state was changed."

Exercise left **paused** with the full stack running.

## Defects found live and fixed (all in `ridge/deploy/local.py` unless noted)

1. **Inventory shapes** — N1 IRIS/CTFd inventories are nested
   (`case.id`, `statuses.open/closed`, `service_user.id`, `identities{team:{id}}`,
   `teams{team:{id}}`); my parser assumed flat keys → `KeyError`. Fixed via shared
   `_derive_discovered`; test fixtures updated to the real shapes.
2. **Relative env paths** — env files rendered relative paths that Compose resolved
   against the compose-file directory. Runtime and asset paths now resolve to absolute
   (`asset()` resolves relative entries against the repo root).
3. **Host bind address** — profile `central_bind_ip` (172.18.0.10) is container-side;
   using it as host publish IP broke the indexer binding. Host publish IP now comes
   from `local.json bind_ip`, default `127.0.0.1`.
4. **`compose ps` missed exited one-shots** — `iris-db-init` (ExitCode 0) was reported
   "absent"; probe now uses `ps -a`.
5. **Health field** — containers without healthchecks report `Status: "Up …"`; probe
   now accepts `Up *`.
6. **`docker cp`/`compose exec` naming** — `docker cp` needs the resolved container
   name (`compose ps -q` + `docker inspect`), while `compose exec` needs the service
   name; both now used correctly.
7. **Guacamole DB name** — actual database is `guacamole`, not `guacamole_db`
   (apply + probe fixed).
8. **Indexer unreachable from host (architectural)** — `compose.wazuh.yaml` puts
   `wazuh-backend` on `internal: true` by design (README: "only the dashboard is
   exposed"); a container attached only to an internal network **silently never
   publishes** host ports on Docker Desktop (reproduced with plain nginx). Evidence
   apply/probe therefore runs as `indexer_job` inside the integration image attached
   to the backend network, with the live `ridge/` tree mounted read-only. The saved
   views still go to the host-published dashboard (8443).
9. **Controller preflight from host impossible** — preflight needs internal IRIS/CTFd
   URLs and the indexer. It now runs via `compose exec integration python -m
   ridge.cli preflight` (the controller container spans both networks and holds the
   bridge secrets). `secret()` needs `RIDGE_*_FILE` env vars — fixed accordingly.
10. **Resume swallowed by wrong exception type** — a runner error from preflight
    escaped as non-`LifecycleError`, bypassing the STOPPED-resume reopen path; now
    wrapped.

## Image identities

Unchanged from N3 (source fingerprint `e03fce5b…`); no image was rebuilt in N4.

## Deferred / limitations (honest)

- `restore` and `switch` are deliberate refusals; N5 (cards D02–D04/E03–E05) owns
  native-database + workspace backup/restore and provider fencing.
- `indexer_job` mounts the **live** `ridge/` source read-only over the image snapshot
  so the new module is available without an image rebuild; for the event, consider
  rebuilding the integration image so provisioning runs from the fingerprinted image.
- E02 `ridge.ps1` was live-tested only through `prepare` on this already-provisioned
  host; a clean-host end-to-end run (fresh Windows + Docker Desktop) is still undone.
- The indexer port-publish no-op on internal networks produced **no daemon error**;
  probes in this repo verify real readiness, which is what caught it. Keep probes
  authoritative.
