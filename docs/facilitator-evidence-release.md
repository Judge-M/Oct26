# Facilitator evidence-release runbook

The expanded event does not release follow-up evidence from the CTFd or IRIS
administrator web pages. Follow-up evidence is released automatically by the
controller integration when the prerequisite ticket chain is complete and its
queued deliveries have synchronized.

## Release chain

| Ticket | Prerequisite(s) | Evidence released when the ticket is created |
|---|---|---|
| T07 | T06 | `identity/late-auth.csv` |
| T09 | T08 | `server/version-comparison.csv` |
| T11 | T10 | `hunting/late-inventory.csv` |
| T19 | T01 and T05 | `network/dlp-body.txt`, `network/dlp-metadata.json` |
| T20 | T07, T09, T11 and T19 | No additional file; final synthesis ticket |

When the last T20 answer closes the final ticket, the controller also emits one
idempotent final-assessment delivery. It is attached to the T20 task in IRIS,
appears as the final announcement on both participant surfaces, and unlocks the
containment-focused conclusion. Do not create a duplicate comment manually.

The initial evidence is published during provisioning. The controller keeps
future material under the private release vault. When a prerequisite closes,
the state worker queues the dependent ticket; the integration worker verifies
the release manifest and SHA-256 values, copies the approved files atomically
into the participant evidence tree, indexes released CSV records into the
dedicated `silent-ridge-*` Wazuh index, and then creates the corresponding IRIS
task. A ticket is not considered released until its delivery is acknowledged.

## Operator procedure

Run these commands on the private integration/controller host, using the
event's actual state path:

```text
python -m ridge.cli --state RUNTIME/state/state.sqlite status
python -m ridge.cli --state RUNTIME/state/state.sqlite diagnostics
```

After the prerequisite ticket is fully answered:

1. Confirm the prerequisite is `complete` and the dependent ticket is no
   longer `locked` in `status`.
2. Confirm `pending` returns to zero. A nonzero value means the worker still
   has deliveries to process; do not manually copy files or attach IRIS tasks.
3. Check the integration, IRIS, CTFd, and Wazuh service logs if `pending`
   remains nonzero. The worker retries safely after connectivity or service
   recovery.
4. Confirm the new ticket appears in the shared IRIS queue and that its named
   files are visible in the read-only participant evidence tree.
5. Announce the operational change only if teams need context; announcements
   are separate from evidence publication:

   ```text
   python -m ridge.cli --state RUNTIME/state/state.sqlite announce \
     --operator EXCON-A --text "Follow-up evidence is now available in the shared queue."
   ```

After T20, confirm `pending` returns to zero and verify the T20 task contains
the **FINAL INCIDENT ASSESSMENT** comment. Use
[`facilitator-closing-brief.md`](facilitator-closing-brief.md) for the spoken or
room-wide audiovisual debrief. Do not expose a participant playback link.

For a technical failure, pause the exercise before intervention:

```text
python -m ridge.cli --state RUNTIME/state/state.sqlite mode paused --operator EXCON-A
python -m ridge.cli --state RUNTIME/state/state.sqlite diagnostics
```

Resume only after the service and delivery queue are healthy:

```text
python -m ridge.cli --state RUNTIME/state/state.sqlite mode running --operator EXCON-A
```

## Important safeguards

- The CTFd/IRIS administrator accounts are for application administration and
  health checks; they do not bypass ticket dependencies or publish future
  evidence.
- Never copy files from the private vault into the participant share manually.
- Never award points, create duplicate tickets, edit receipts, or close tasks
  by hand. The outbox and application receipts make retries idempotent.
- Before production, reset the entire event using the documented clean-run
  procedure; do not reuse this rehearsal's state, scores, awards, or team
  workspaces.
