# Operation Silent Ridge — Operator Runbook

Audience: the event operator. No prior conversation or build history assumed.
Everything here is a drill-tested command; where a step has not been run on the
event hardware yet, it says so. One page of event-day instructions, recovery
appendices after.

Conventions: `P` = your profile JSON (copy of
`deployment/profiles/example-dynamic.json`, adjusted), `R` = your private
runtime directory (secrets, state, inventories — never commit it, never give it
to participants). Windows operators may use `.\ridge.ps1 <action> -Profile P
-Runtime R` instead of `python -m ridge.deploy`.

## Event day, in order

1. **Verify the host and deployment inputs** — `python -m ridge.deploy doctor
   --profile P --runtime R`. It checks Docker, the profile, build receipts,
   images, assets and `RIDGE_BACKUP_KEY`; when the stack is up it also reports
   live stage probes. Without `--profile`, doctor checks Docker only.
   Hardware floor for ten teams, from live measurement: 32 GB RAM
   minimum (64 GB comfortable), 16 cores recommended, 100 GB free NVMe.
2. **Bring the stack up** — `python -m ridge.deploy up --profile P --runtime R`.
   Ends at `PROVISIONED_PAUSED`; participants see nothing yet. Safe to re-run:
   it re-probes, it never resets state.
3. **Check readiness** — `python -m ridge.deploy status --profile P --runtime R`.
   You want `event_ready: true`, all stages verified.
4. **Prepare check-in** — project opening slide 5. It already shows both:
   - registration address: `https://ctfd.cyberexperts.org/silent-ridge/register`
   - enrollment code: `SILENT-RIDGE`
   Facilitator and participant passwords remain random and must never be
   replaced with `admin/admin` or `teamN/teamN`.
5. **Start the exercise** — run
   `python -m ridge.deploy start --profile P --runtime R`. Registration uses
   the enrollment code as its only gate; there is no separate open/close step.
   Each private retrieval page supplies five CTFd seats and the team's IRIS,
   Wazuh, Guacamole, and three desktop connection details.
6. **During play** — announcements:
   `python -m ridge.cli --state R/state/state.sqlite announce --operator YOU --text "..."`.
   Free a stuck ticket:
   `python -m ridge.cli --state R/state/state.sqlite recover T03 --team team-03 --generation N --operator YOU --reason "..."`
   (take `N` from `status`; solved answers and points are kept).
7. **Breaks / end of play** — `python -m ridge.deploy pause --profile P --runtime R`.
   The clock freezes; findings and scores persist.
8. **After the AAR, back up** — `python -m ridge.deploy backup --profile P --runtime R`
   → a checksummed recovery set under `R/backups/<timestamp>/`. It is complete
   only when it contains `RECOVERY-COMPLETE.json`.
   Set `RIDGE_BACKUP_KEY` to a private, persistent value of at least 16
   characters **before the event**. Keep the same value available for restore;
   it is never saved in the runtime or recovery set. Doctor reports whether it
   is present without printing it, as `recovery_ready` — deliberately separate
   from `ready_for_up`, because the key is not an input to `up` and a missing
   key is not a reason to hold off on the first deployment. A missing key
   refuses backup before export.
9. **Shut down** — `python -m ridge.deploy down --profile P --runtime R`
   (data kept). Add `--volumes` only when you mean it: it wipes all event data
   and **refuses unless a verified backup exists**.

Participant URLs in the public-certificate event configuration are
`https://guac.cyberexperts.org`, `https://iris.cyberexperts.org`,
`https://ctfd.cyberexperts.org`, and `https://wazuh.cyberexperts.org`, all on
port 443. Generated-CA fallback ports and its CRL are documented separately in
`docs/participant-ca-trust.md`.
All four open in the participant's own laptop browser — the
remote desktop is only needed for the native tools (Autopsy, Wireshark,
Cutter, file manager), so steer participants away from browsing inside it:
an in-desktop Firefox costs the shared desktop roughly another gigabyte and
adds VNC lag.

## Symptom → diagnostic → action

| Symptom | Diagnostic | Action |
|---|---|---|
| `up` reports a stage probe error | `status` names the stage and cause | Re-run `up`; it reconciles that stage only. It never silently recreates state |
| `start` refuses | A stage is unverified or preflight failed | `status` shows which gate; fix, re-run `up`, then `start` |
| Team can't claim a fresh ticket | "still being prepared in IRIS; retry shortly" | Transient — the IRIS task is being created; retry in a few seconds |
| Answers accepted but no points showing | Outbox backlog: worker logs (`docker logs <event>-integration-1`) | Fix connectivity/credentials; the worker retries — do **not** re-award points or edit receipts |
| A team disconnects mid-ticket | Its queue shows the ticket active | `ridge.cli --state R/state/state.sqlite recover <ticket> --team <team-id> --generation N --operator YOU --reason "..."` releases only that team's lane |
| Registration stays pending or says operator help is needed | `registration-status` shows the row and attempt count | Fix the named service, then use `registration-retry --registration-id N`; rotate a lost retrieval link with `registration-rotate-link` |
| Desktop sluggish | Host CPU/RAM saturated (`docker stats`) | Pause non-critical team work; stagger Autopsy ingests; do not restart containers mid-event |
| Anything feels lost | Don't improvise | `backup`, then Appendix B |

## Appendix A — Private credentials and backups

- All secrets live only under `R/` (env files, `secrets/`, `inventories/`).
  Dynamic-team accounts are retrieved through each team's private registration
  link; the runtime files are operator recovery material, not handouts. None of
  this is in git.
- Backups: `R/backups/<UTC timestamp>/`, each with `manifest.json`,
  `SHA256SUMS.json`, and `RECOVERY-COMPLETE.json` when complete. Secrets inside
  a recovery set are encrypted (`RIDGE_BACKUP_KEY` env at backup/restore time;
  the key is never stored in the set).
- Retention: older sets are pruned only when the newest set verifies.

## Appendix B — Recovery

Full wipe and restore (drill-tested: backup → `down --volumes` → restore →
participants kept playing, scores intact):

```bash
python -m ridge.deploy down --volumes --profile P --runtime R
python -m ridge.deploy restore --from R/backups/<timestamp> --profile P --runtime R2
```

`R2` must be an empty/new runtime directory. Restore refuses a dirty
destination, live containers, a corrupt set, or a release mismatch — unless you
pass `--accept-release <exact fingerprint>` (it then migrates the schema) or
`--degraded-ok` (skips unreadable volume archives and **names** the data loss
in the result; never silent).

`switch` (moving to a second site) is intentionally not available in the local
build — it arrives with the AWS provider. `fence` stops a site's mutations
before any destination activation: `python -m ridge.deploy fence --profile P
--runtime R`.

## Appendix C — Offline cache verification

Installing from an offline release bundle (USB/off-network host):

```bash
python -m ridge.offline_install <bundle-dir> <install-dir>
```

Every part is hashed before anything changes; missing/corrupt parts, LFS
pointer stubs, low disk, or interruption fail cleanly and leave no partial
install. The installer materializes all five asset trees, creates build
receipts for the four custom images, and writes `runtime-local.example.json`.
Run deployment commands from `<install-dir>/source`; load results and the exact next commands are in
`<install-dir>/install-receipt.json`. A bundle whose `install-receipt` shows
`certified_complete: false` is drill material, not a certified release.

## Appendix D — Cost inventory

Local provider: no retained cost — `down` leaves only Docker volumes on the
host; `down --volumes` removes them. AWS provider: not yet built (E03–E05);
its teardown/cost verification is part of that work and must be complete
before any cloud run.

## Known limitations (as of this writing)

- Ten-team capacity and the 4–5 h duration are model-backed but not yet
  rehearsal-proven on the event hardware (F03/F06 pending).
- AWS provider, site switch, and off-box backup copy are not built.
- The Windows launcher `prepare` path is verified on this host only; a
  clean-host run is scheduled with the cold-cache install test.
