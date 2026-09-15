# Controller operations and recovery

The expanded exercise has no report, grading or facilitator-approval gate. IRIS
contains native shared tasks and automatic findings. Team ownership mutations
originate in its queue extension; CTFd's extension presents current questions and
completed shared history. IRIS is the only participant ticket system.

## Start, pause and announcements

Run these on the private integration/controller host using its configured state:

```text
python -m ridge.cli mode running --operator EXCON-A
python -m ridge.cli mode paused --operator EXCON-A
python -m ridge.cli announce --operator EXCON-A --text "Exercise paused for technical recovery. Revised activity end is 14:40 local."
python -m ridge.cli status
```

The core elapsed clock sums running intervals. Participant views advance between
server snapshots and resynchronize every five seconds. Published announcements
are persistent and visibly separate from findings. A private note is not a public
deadline change. Keep controller planning/solutions outside the public evidence
share. The full audit/export is private; the participant snapshot contains only
published announcements, visible ticket state and scores.

Narrative developments are currently published manually with `announce`; there
is no automatic timed-announcement scheduler in the expanded implementation.
Plan optional narrative updates around elapsed 60, 130 and 200 minutes without
using delayed releases to inflate activity time. Teams can investigate independent
tickets immediately. Suggested event plan: 20-minute orientation, 130 minutes of
activity, 15-minute break, 130 minutes of activity, 30-minute AAR. Actual duration
must be validated with beginners.

## Ownership recovery and outages

```text
python -m ridge.cli recover T03 --generation 1 --operator EXCON-A --reason "Team disconnected; release remaining questions for another team"
```

Recovery records the previous owner, operator and reason. Solved answers and
points do not reset. An incorrect answer stores no submitted flag and earns no
points. The core uses serialized SQLite transactions and database uniqueness for
one owner/one active ticket and one globally accepted answer per question.

On accepted answers, the core commits answer state and outbox entries together.
Remote point/finding delivery retries with a bounded backoff. Each application
stores a unique receipt in the same transaction as its side effect. A lost response
after remote commit can therefore be retried without duplication. Findings precede
closure, and closure precedes follow-up creation. The participant view displays
pending synchronization; authoritative accepted state is retained locally.

Delivery is ordered per ticket and across prerequisite closures. An unavailable
destination delays its dependent deliveries while unrelated tickets can advance.
Inspect private `outbox.error`/`attempts` and application logs. Fix connectivity,
credentials or schema mismatch and let the worker retry. Do not manually edit
receipts, award points again, or delete queued events. Schema/runtime behavior of
the application extensions still needs live outage testing.

See [schema-v2 operation](resilience.md) for explicit provisioning, ownership generations,
export barriers, preflight and backup-verified retention. Use the actual generation
from `status` in recovery commands; the example above is not a fixed value.

## Export and reset

Pause the run, freeze native controller edits, and wait for `pending` to reach
zero. Then export all three records together:

```text
python -m ridge.export_run --state runtime-expanded/state.sqlite PRIVATE-EXPORT-DIRECTORY
```

This exports IRIS tasks/comments/links/receipts, CTFd awards/receipts and the complete
integration mappings, answers, ownership history, outbox and timing audit. A final
checksum manifest marks successful export. A directory without that manifest is
incomplete. Credentials are not exported, but answer hashes and participant data
make the export private. Also take native IRIS/CTFd/Guacamole database backups,
Wazuh index snapshots and team workspace/case backups for disaster restoration.

No destructive global reset command is supplied. For a clean run, stop the stacks;
retain/export the existing databases and workspaces; allocate new volume names,
a new IRIS case and clean CTFd database; provision identities; initialize a new core
state path; restore only initial evidence/indexes and fresh per-team case copies.
Old volumes remain available for recovery. Never reuse the prior CTFd awards table
as a clean scoreboard or silently discard participant work. This full reset/restore
procedure has not been executed here.

## Offline package

Keep VM images, disk/memory files, cases, dependency archives and container saves
in the designated artifact store. `expanded/manifest.example.json` is intentionally
incomplete. Populate path, category, version, release, byte count and SHA-256 for
every artifact, plus the validated source commit. Complete-bundle verification is:

```text
python -m ridge.artifacts ARTIFACT-STORE VERSIONED-MANIFEST.json
```

Transfer and verify the trusted manifest separately. `--allow-incomplete` checks
integrity only and must never be treated as release readiness. The old image
packager now checks actual application-image contents against source before
packaging, but it packages only the retired two-service stack. It is not the
expanded-stack packager. The new `python -m ridge.bundle STORE MANIFEST DESTINATION`
assembler requires a complete validated manifest and clean committed source. It
checks the three extension source layouts inside their exact images and saves
all central/dependency images afresh, rather than copying a potentially stale
image archive. Full packaging and offline restore remain unexecuted release gates.
