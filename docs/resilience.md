# Integrity and availability operating procedure

## Upgrade an existing run

1. Pause the old core. Stop integration workers and native controller edits. Back up all three databases, including receipts, and the original content/release manifests.
2. Deploy the new core and both application adapters together. Old ownership forms must be reloaded.
3. Regenerate authored ticket metadata with `python expanded/author.py`. Compare it with the running content before migration; the migration updates only release requirements, not questions, answers, or scores.
4. Run `python -m ridge.cli --state PRIVATE-STATE migrate --content expanded/tickets.json`. The transactional schema-v2 migration preserves existing IDs, receipts and the original queued delivery order. It is repeatable. Do not run old binaries after migration.
5. Prepare a verified `manifest.json` in the release vault root. Regenerating preparation fixtures creates this manifest; never replace live evidence without checking its hashes against the retained release.
6. Run preflight and explicit provisioning before restarting deliveries. All newly initialized and migrated runs have delivery disabled until provisioning.

If the prior run has different ticket identifiers/content, prepare its release requirements explicitly; do not substitute the current scenario. The migration fails on a ticket-set mismatch.

## State transitions

| State | Participant claims/answers/releases | Delivery | Controller operations |
|---|---|---|---|
| Initialized, paused | Rejected | Disabled | Preflight, provision, announcements |
| Provisioned, paused | Rejected | Drains accepted work and initial tasks | Resume, recovery, export after draining |
| Running | Allowed subject to ownership generation | Enabled | Pause, announcements, recovery |
| Export barrier active | Rejected | No pending work permitted | Mutations rejected; explicit cancellation only |

Provisioning intentionally exposes initial tasks/evidence before competition starts. Pausing freezes participant writes, not already published evidence or delivery of accepted work. Keep participant accounts/network access unavailable until orientation if early reading is prohibited. The legacy rehearsal board now rejects comments/status updates before start and while paused too.

## Deployment preflight

Configure all transport and release environment variables on the controller host. Every team configuration needs the actual `iris`, `iris_login`, `ctfd`, and `ctfd_name`. Preflight verifies these against active read-only IRIS case users and visible, unbanned CTFd teams, checks case/status IDs and receipt tables, required initial/release artifacts, free disk space, and read access to the local Wazuh index using normal certificate verification.

```text
python -m ridge.cli preflight
python -m ridge.cli provision --operator EXCON-A
python -m ridge.cli diagnostics
python -m ridge.cli mode running --operator EXCON-A
```

Preflight is not an Autopsy/Guacamole usability test and does not certify write permissions for Wazuh indexing. Rehearse an actual release and every desktop/tool before the event. The manifest is a trusted release input: transfer/verify it with the complete offline bundle, not from a participant-controlled location.

## Delivery and ownership

Each worker reserves an eligible delivery in a short transaction. It renews a 30-second lease every five seconds while performing external work outside the database lock. An expired lease can be reclaimed. Receipts make a late or retried remote application commit safe. A stale worker cannot acknowledge a newer worker's lease.

Events within one ticket remain ordered, and follow-ups depend on prerequisite closure delivery. Unrelated tickets can advance when another chain fails. Retries back off per event to at most 30 seconds; failed work is never silently dropped. Initial v1 queued work retains its conservative global ordering during migration.

Use private diagnostics for oldest pending age, failed event kinds/attempts, and the export token. `/health` reports a database/worker or recorded delivery failure without exposing payloads. A health failure alerts operators; it is not authorization to delete state or receipts. SQLite/local integration-host failure remains a single point of failure requiring coordinated backups.

Claims and relinquishments carry the displayed ticket generation. To recover a ticket, first read `status`, then pass that exact generation:

```text
python -m ridge.cli recover T03 --generation 2 --operator EXCON-A --reason "Disconnected team"
```

A delayed old form cannot claim or relinquish a later ownership generation. A lost successful answer response may still return a conflict on retry; accepted points remain in the authoritative snapshot.

## Export fencing

Pause and drain, freeze native application writes, then use `ridge.export_run`. It holds a durable core barrier across all snapshots, verifies application receipt watermarks against the core, and writes the checksum completion marker only while it still owns the barrier. Network errors leave an incomplete directory and release the barrier normally.

After process death, the barrier remains in place. Verify the exporter is stopped and discard its incomplete output before running:

```text
python -m ridge.cli cancel-export --token EXACT-TOKEN-FROM-DIAGNOSTICS --operator EXCON-A
```

Cancellation prevents that exporter from subsequently marking success. This barrier cannot fence direct database/native controller writes; those must stay frozen operationally. Keep native database backups for disaster restoration.

## Evidence and capacity

The generated vault manifest declares every required release file and hash. Missing required files fail before an IRIS task is created. Publication verifies staged copies and completes indexing before placing files at their final paths. Index batches contain at most 100 records with stable IDs; partial failures retry safely. Publication is atomic per file, not across a filesystem and Wazuh. Crash-partial evidence can be visible, but the ticket cannot be claimed until all components succeed.

Do not remove the explicit `release_files` declaration. Tickets using only initial evidence declare an empty list. Timeless coverage/catalog facts no longer receive fabricated occurrence timestamps; inspect them in a Wazuh data view without a time field. Scenario dates come from the expanded configuration; historical endpoint addresses remain separate from infrastructure addresses.

Publication and export require 1 GiB free headroom by default, configurable with `RIDGE_MIN_FREE_BYTES`. These checks are admission checks, not filesystem quotas. Set host/volume quotas for team Cases, Workspace and Scratch directories and monitor database/index/volume usage separately.

```text
python -m ridge.storage PRIVATE-EXPORT-ROOT
python -m ridge.storage PRIVATE-EXPORT-ROOT --backup SEPARATE-BACKUP-ROOT --retention-days 30
python -m ridge.storage PRIVATE-EXPORT-ROOT --backup SEPARATE-BACKUP-ROOT --retention-days 30 --apply
```

The second command is a dry run. Pruning accepts only completed three-system exports with matching independently verified backups and no extra files or symlinks. It never deletes native volumes, legacy ZIP exports, active runs, or team cases. Stop writers before pruning. Handle those other retention categories through the host's explicit backup/retention policy. Inspect abandoned `.ridge-release-*` staging directories and incomplete exports while workers are stopped; they are not eligible for automatic completed-export pruning.

## Validation boundary

Portable regression tests cover blocked/stale ownership, concurrent workers, lost/expired leases, database availability during remote I/O, export fencing, release failure, bulk response validation, alternate dates, DNS agreement, reproducible fixtures, and backup-verified retention. The CTFd container smoke additionally covers failed cache invalidation after award commit. Full IRIS/PostgreSQL, CTFd/MariaDB/Redis, Wazuh, Guacamole, and Autopsy outage/restore rehearsal remains required.
