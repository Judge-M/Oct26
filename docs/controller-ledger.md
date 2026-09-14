# Controller clock and acknowledgments

The fallback retains five cell identities. Cells can request actions in comments,
but cannot approve them. The authoritative decision record is an external ledger
written through the controller host CLI, under the operator's OS account. Each
record has a CTL ID, actual UTC, pause-aware elapsed seconds, named operator alias,
host username, event kind and details. Use individual OS accounts where independent
person-level attribution is required. The alias alone is not authentication; do not
share host accounts for assessed controller attribution. Restrict runtime/control,
the repository and host/Docker access to trusted controllers. This is a procedural
audit ledger, not a cryptographically immutable or tamper-proof record.

The participant application mounts control read-only and exposes only authenticated
GET /api/control. It has no ledger-write, release or reset HTTP endpoint. The UI
displays controller records separately from cell comments. Cells cite CTL IDs when
reporting acknowledged actions. A cell comment that says “approved” has no authority.
Jira users reference the same ledger, optionally mirrored by a named controller's
own Jira account. Do not put hidden solutions or future inject contents in notes:
the whole ledger is visible to participants.

Run commands from the repository root, with the exercise server running if desired:

```text
python scripts/exercise.py start --operator EXCON-A --text "All five cells ready"
python scripts/exercise.py pause --operator EXCON-A --text "Resolve projector failure"
python scripts/exercise.py resume --operator EXCON-A --text "All cells ready to resume"
python scripts/exercise.py release 1 --operator EXCON-A
python scripts/exercise.py decision --operator EXCON-A --request T1-C12 --outcome approved --effective-minute 48 --text "Isolate WS-17; clerk access interruption accepted; preserve volatile evidence; verify isolation"
python scripts/exercise.py note --operator EXCON-A --text "Inject 1 released late; response now due at elapsed minute 55; announced to all cells"
python scripts/exercise.py export
```

Decision outcomes are approved, denied or pending. Approved decisions require an
effective elapsed minute inside the run. That is simulated action time, distinct
from when the operator records the decision; retrospective decisions must explain
the difference in text. Reference the request using fallback T<ticket>-C<comment>
or the Jira issue/comment ID. A new decision superseding an earlier one must cite
its CTL ID in text; do not rewrite earlier entries. The hunting reporter records the
joint assessment on ticket 5 and the controller acknowledges receipt with a note.

Start is permitted once. Pause freezes elapsed time; resume continues it. Actual
UTC is always recorded, including during pauses. A backwards host clock is rejected;
resolve time synchronization before recording more events. Planned scenario clock
equals 09:30Z plus elapsed time, separate from unchanged historical evidence times.
Release before clock start is allowed for technical rehearsal and is explicitly
recorded with null elapsed time; start the clock before any assessed event.

Fallback comments display Tn-Cn, actual UTC, captured elapsed seconds and the latest
CTL event used when posted. Older comments without clock data display unavailable;
do not invent elapsed times. The ledger allows reconstruction of Jira comment UTC
times: sum running intervals since start, excluding pause/resume intervals. Before
start, elapsed is undefined. The app's exercise_clock.elapsed_at implements this rule.

Only one host command may write at a time; an exclusive control.lock prevents
concurrent releases/decisions. The lock file records the holder's pid, host and
acquisition UTC, and the conflict error prints them so an operator can judge
whether the holder is dead before clearing the lock; it is never removed
automatically. Pause ledger writes and releases during export to keep
the SQLite snapshot, ledger, manifests and release log aligned. The export includes
control/ledger.json and comment clock fields. Archive individual operator attribution
privately with participant work.

Verification requires exact initial-manifest bytes, exact released bundles including
their manifests, sequential released directories, and matching release events/logs.
A crash between directory rename and ledger/log writes fails verification. Stop
releases, preserve the runtime/export and inspect the interruption; restore a known
consistent private backup or reset for a new rehearsal. Never “repair” a failure by
regenerating a public manifest. The vault is the trusted canonical boundary; host
controllers must protect it and retain the offline package checksum manifest.
