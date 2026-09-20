# N5 Receipt (Slice A) — Recovery Sets, Restore, Retention, Fencing (cards D02/D03/D04/F01)

Date: 2026-09-20. Branch: `feat/n5-recovery-fencing`. Base: `main` after N4 merge (PR for N4).
Test count: **256 passing** (was 240 after N4; +16 recovery/fencing).

Scope: N5 per `NEXT.md` spans D02–D04, E03–E05, F01–F06, G01, H01. This slice delivers
**D02, D03, D04, F01** — everything implementable and verifiable locally. Blocked and
remaining contracts are named at the end.

## What was built

- **`ridge/schema.py` v3** — adds `control.fenced` (0/1) and `control.site_generation`
  (monotonic integer). v1→v2→v3 migration chain preserved; the live drill state was
  migrated in place with `python -m ridge.cli … migrate` before backup.
- **`ridge/state.py`** —
  - `mutable()` now raises `Conflict` when the site is fenced (control-plane mutations
    fail closed while fenced);
  - `fence(actor)` requires paused exercise + drained outbox, sets `fenced=1`, journals
    `FENCED`; `unfence(actor)` is an explicit operator rollback;
  - `activate_generation(actor, generation)` is monotonic and never activates on a
    fenced site (F01 generation semantics for future site switchover);
  - `site_info()` exposes fencing/generation for status surfaces.
- **`ridge/deploy/recovery.py`** (new, ~520 lines) —
  - **D02 `create()`**: refuses unless paused + outbox drained. Produces a timestamped
    recovery set: watermark export (one-shot integration container on
    `<event>-central` running `python -m ridge.export_run`; takes its own export
    barrier in-container — the host-side barrier is deliberately not held, a double
    barrier deadlocks), SQLite backup-API copy of state + journal, DB dumps
    (`pg_dump -Fc` iris_db, `mysqldump` ctfd, `pg_dump` guacamole — written
    in-container then `docker cp`'d out; stdout capture corrupts binary dumps),
    Wazuh index NDJSON dump (`indexer_job dump`), volume tars (closed via
    `with tarfile.open(...)` + post-write readability probe), evidence tree, release
    vault, and secrets/specs/wazuh-certs inside `secrets.tar.gz.enc`
    (openssl AES-256-CBC PBKDF2, key from env `RIDGE_BACKUP_KEY`, **never** stored in
    the set — manifest carries a key *reference* only). `manifest.json` (schema 1)
    records event, release fingerprint, site generation, volume list, team list.
    `SHA256SUMS.json` is written, verified, and only then `RECOVERY-COMPLETE.json`
    is stamped — a set without the marker is not a recovery set. `verify_set` is
    fail-closed.
  - **D03 `restore()`**: refuses a dirty destination runtime (only `local.json` may
    pre-exist), refuses live containers, refuses corrupt/incomplete sets, and refuses
    a fingerprint mismatch unless `--accept-release <exact fp>` is given — in which
    case the restored state is run through `schema.migrate` before bring-up
    (cross-release restore path). Restores secrets/specs/certs/state/inventories,
    brings up databases, waits healthy, replays dumps (`docker cp` +
    `pg_restore --clean --if-exists` / `mysql <`), untars volumes (unreadable
    archives abort; with `--degraded-ok` they are skipped and **named** in
    `result['data_loss']`), applies Wazuh index + loads NDJSON, restores
    evidence/vault trees, then delegates to `stack.up(...)`. On failure it stops any
    event containers so a retry does not trip the live-container refusal.
  - Volume inventory: `data_volumes()` = iris-data, iris-templates, iris-downloads,
    ctfd-uploads, ctfd-logs; `team_volumes()` = `<event>-desktops_team%02d-{cases,
    workspace,scratch}`.
- **`ridge/deploy/indexer_job.py`** — added `dump` (scroll → NDJSON with stable
  `_id`s) and `load` (NDJSON bulk; `_transport` gained `raw=` support). The job image
  does not embed this module, so `_indexer_job` mounts the live `ridge/` tree
  read-only over `/opt/silent-ridge/ridge`.
- **`ridge/deploy/local.py`** —
  - `backup()` → `recovery.create()` (cipher/export_job injectable);
  - `fence()` → `state.fence()` + stops integration/desktops projects + journals
    `FENCED` (F01 local authority: state control table + journal; cloud fencing is
    E04, blocked);
  - `down(volumes=False)` — with `--volumes`: compose-down per project first
    (stopped containers still block `volume rm`), then **refuses unless a verified
    recovery set exists** under `runtime/backups`, then removes all event-owned
    volumes. Without `--volumes` behavior is unchanged (volumes kept);
  - `restore()`/`switch()` still refuse without `--from`; with `--from` they dispatch
    to `recovery.restore()`;
  - `release_fingerprint` is set in `up()` and recovered from journal meta in
    `backup()`.
- **`ridge/deploy/__main__.py`** — new action `fence`; new flags `--from`,
  `--degraded-ok`, `--accept-release`, `--volumes`.
- **`ridge/storage.py`** — `verified_recovery_set()` / generalized `verified_set()`
  (accepts the `RECOVERY-COMPLETE` marker); `prune` (D04) only prunes when the latest
  set is verified — a corrupt or missing backup blocks pruning; unknown directories
  are never touched.
- **Tests**: `tests/test_recovery.py` (16 tests: layout, sums, incomplete-set
  refusal, dirty-runtime refusal, live-container refusal, degraded restore naming
  data loss, fencing semantics, retention gating); `tests/test_deploy_lifecycle.py`
  extended (FakeRunner docker ps/volume/tarfile/dump-load branches, FakeCipher,
  fake export job).

## Live drill (real stack, profile `work/n4-run/profile.json`)

Sequence actually executed on the adopted N1/N3 stack:

1. **In-place schema migration** of live state to v3 (`ridge.cli migrate`, content
   derived from the tickets table).
2. **D02 backup** → `work/n4-run/backups/20260920T010801Z`, 62 files, real
   watermarks (IRIS receipts/tasks, 1 CTFd credit), manifest above, RECOVERY-COMPLETE
   stamped after sum verification.
3. **Destructive teardown**: `down --volumes` wiped **all** event volumes and
   containers.
4. **Cross-release restore**: N3-built images embed schema v2 while the restored DB
   is v3 (worker crash-looped on diagnostics). Fixed by rebuilding
   (`python -m ridge.deploy build --component all`) → new source fingerprint
   **`330ee73b391186e73211be3b4766a23bc34cb8371a22d8ae4beea5add2457154`**, image IDs
   iris `75b27db0`, ctfd `998dcee4`, integration `5b132169`, desktop `3083fcf7`
   (previous fingerprint `e03fce5b…`). Restore then completed with
   `--degraded-ok --accept-release e03fce5b…` onto runtime `work/n5-restore/`,
   reaching **PROVISIONED_PAUSED**; preflight OK; Wazuh index reloaded to
   **511 documents = pre-wipe count**.
5. **Equivalence check**: answers/tickets/teams/outbox rows identical to
   `work/n5-pre-wipe-facts.json`; repeated `up` idempotent; control row
   `fenced=0, site_generation=1`; desktop team01 auto-reseeded
   `/home/participant/Cases/WS17/WS17.aut` and `/evidence/network/sensor.pcap`
   via the entrypoint seeder.
6. **D03 acceptance — post-restore solve**: `start` → RUNNING; `team-01` answered
   `T02-Q1` correctly through `State.answer()`; integration worker drained the outbox
   (`point` + `finding` both `done=1`); CTFd shows new credit
   `d81dac54…:point:T02-Q1` (award_id 3) and IRIS shows receipt
   `d81dac54…:finding:T02-Q1` (remote 8). Exercise then paused
   (PROVISIONED_PAUSED).

## Data loss in the drill — stated plainly

The backup set's **volume tars were corrupt** (~30-byte stubs): an early revision of
`create()` opened tarfiles without closing them, and SHA256 sums cannot catch
semantic truncation of a freshly-written file. Discovered only after the volumes were
wiped. Lost: `iris-data` (IRIS app uploads/custom assets — case data itself lives in
postgres and survived), team workspace/scratch content from N3, and team cases
(which re-seed automatically via the entrypoint). `iris-downloads` was verified
empty and removed manually.

Fixes landed in this branch so it cannot recur:

- tarfiles are written under `with tarfile.open(...)` (closed + flushed) and each
  tar is **re-opened and read back** inside `create()` before the set is stamped;
- `restore()` probes every archive's readability and aborts (or names the volume in
  `data_loss` under `--degraded-ok`) instead of silently applying empty archives;
- unit tests cover both the readability probe and the degraded path.

The restore was therefore degraded in the precise, declared sense: the skipped
volumes are named in the drill output, everything else is byte-equivalent.

## Fencing semantics (F01, local slice)

- Fencing authority is the state `control` table plus the deploy journal; `fence`
  requires paused + drained and stops mutation-bearing projects; all control-plane
  mutations fail closed while fenced; `unfence` is an explicit operator action.
- Cloud-side fencing (revoking the old site's AWS credentials/routes) is contract
  E04 and is **not** part of this slice — see below.

## Blocked / remaining contracts

- **E03–E05 (AWS accounts, cloud fencing, site switchover)**: blocked — no AWS
  account/credentials/budget on this machine, and this machine is not the event
  host. `--accept-release` + `activate_generation` give E05 its local hooks.
- **F02 (off-box backup copy)**: depends on E04 credentials; blocked.
- **F03 (capacity rehearsal at event scale)**: requires the event hardware; this
  32-GiB dev box is explicitly out of scope per the card.
- **F04 (duration-gap analysis), F05 (runbook), F06 (full rehearsal), G01
  (scoreboard), H01 (handoff pack)**: remaining N5 work, none blocked by this slice.

Per `NEXT.md`, this PR should receive an independent focused review of
restore/deletion/fencing semantics (Copilot review requested on the PR).
