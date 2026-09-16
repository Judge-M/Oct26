# Silent Ridge operator runbook (G01)

Drafted 2026-09-16 on `lane/review-h01` from the accepted commands in this tree. This
runbook is **not yet validated by a second operator or a real two-team smoke**; G01
acceptance requires that and is BLOCKED without event hardware. Treat every command
below as source-tested only where noted.

## One-page event day

```powershell
.\ridge.ps1 -Action prepare -Event ridge-oct26 -Profile .\profiles\event-local.json -Release vX.Y.Z
.\ridge.ps1 -Action up      -Event ridge-oct26 -Profile .\profiles\event-local.json -Release vX.Y.Z
.\ridge.ps1 -Action status  -Event ridge-oct26
.\ridge.ps1 -Action start   -Event ridge-oct26
.\ridge.ps1 -Action pause   -Event ridge-oct26
.\ridge.ps1 -Action backup  -Event ridge-oct26 -Destination D:\backups\ridge-oct26
.\ridge.ps1 -Action down    -Event ridge-oct26
```

`up` leaves the exercise paused unless `-Start` is passed. It never resets an existing
event. Linux uses the same operations through `python -m ridge.deploy`.

## Command reference and status

| Command | Module | Source status | Live status |
|---|---|---|---|
| `ridge.ps1` launcher | `ridge.ps1` (E02) | tested on Windows | blocked: needs prepared host |
| `python -m ridge.deploy prepare/up/status/start/pause/backup/restore/down` | `ridge/deploy.py` (E01) | tested with an injected provider | blocked: A03/A04 provider PENDING |
| recovery set / restore | `ridge/recovery.py` (D02/D03) | tested | blocked: needs live app DBs |
| retention | `ridge/retention.py` (D04) | tested | dry run only |
| AWS image/infra/teardown | `ridge/aws_image.py`, `ridge/aws_infra.py`, `ridge/aws_teardown.py` (E03–E05) | command builders tested | blocked: no AWS account/credentials |
| fencing / switching | `ridge/fencing.py`, `ridge/switching.py` (F01/F02) | tested | blocked: needs two live sites |
| capacity / learning / offline release / rehearsal | `ridge/capacity.py`, `ridge/schedule_model.py`, `ridge/offline_release.py`, `ridge/rehearsal.py` (F03–F06) | evaluators tested | blocked: needs deployed stack and humans |
| portable build pipeline | `buildpipe/` (H01a–e) | tested | desktop stages blocked: no Linux/qemu |

## Symptom → diagnostic → action

| Symptom | Diagnostic | Action |
|---|---|---|
| `up` refuses with "different release" | `python -m ridge.deploy status --event <id>` shows the bound release | Freeze a new version; never overwrite an existing event. |
| `up` refuses with "event lock" | Another process holds `work/events/<id>/lock` | Confirm no other operator is running; remove a stale lock only if the PID is gone. |
| `start` refuses "before every readiness step" | `status` lists `pending` steps | Re-run `up`; fix the failing component; do not bypass. |
| "Missing artifact"/"Readiness check failed" | `status` shows `probe`/`health` | Restore the artifact or credential named in the error; the journal is preserved. |
| Backup not marked restorable | `ridge/recovery.py` leaves no `RESTORABLE` marker | Re-run backup; a partial set is never restorable. |
| Teardown refuses | `status` shows no verified backup | Run `backup` first, or pass `--retain-backup` only with an approved retention policy. |
| Stopped EC2 appears free | `ridge/aws_teardown.py` cost report | Stopped instances still incur EBS/EIP cost; review `cost_categories`. |

## Private material and locations

- Private profile: `profiles/event-<provider>.json` (never committed).
- Core journal and receipts: `work/events/<event>/`.
- Recovery sets: the configured private backup root; secret material is encrypted
  separately (`ridge/recovery.py`) and is never inside a public release.
- Build secrets: `work/secrets/` and `work/dependencies/`, outside `release_root`
  (`buildpipe/pipeline.py`).
- Credential handout and access URL: produced by the provider after readiness (A04,
  PENDING). The launcher refuses secrets on the command line.

## Offline cache verification

```text
python -m buildpipe run --config build.json --work work
python -m ridge.offline_release   # merge/pin/verify helpers (F05)
```

Verify that no Git LFS pointer stubs remain and every image is pinned to a `sha256`
digest. `ridge/offline_release.py` refuses mutable tags and incomplete categories.

## Retained-cost inventory after teardown

`ridge/aws_teardown.py` reports `planned`, `deleted`, `retained` and
`cost_categories`. A stopped instance is reported under `stopped_compute_ebs`, not as
zero cost. `expiry_check` requires an approved TTL before any automated teardown.

## Known limitations (must be resolved before event approval)

- No real deployment provider (A03/A04) is wired; the CLI cannot reach
  `PROVISIONED_PAUSED` against live infrastructure.
- No live backup/restore, AWS import/teardown, provider switch, capacity measurement,
  offline install or dress rehearsal has been executed.
- The ten-team duration gap (F04) is an arithmetic estimate until a human rehearsal is
  recorded.
- This runbook has not been followed end to end by a second operator.
