# Operation Silent Ridge — Operator Runbook

Audience: the event operator. No prior conversation or build history assumed.
Everything here is a drill-tested command; where a step has not been run on the
event hardware yet, it says so. One page of event-day instructions, recovery
appendices after.

Conventions: `P` = your profile JSON (copy of
`deployment/profiles/example-two-team.json`, adjusted), `R` = your private
runtime directory (secrets, state, inventories — never commit it, never give it
to participants). Windows operators may use `.\ridge.ps1 <action> -Profile P
-Runtime R` instead of `python -m ridge.deploy`.

## Event day, in order

1. **Verify the host** — `python -m ridge.deploy doctor` (Docker present and
   responding). Hardware floor for ten teams, from live measurement: 32 GB RAM
   minimum (64 GB comfortable), 16 cores recommended, 100 GB free NVMe.
2. **Bring the stack up** — `python -m ridge.deploy up --profile P --runtime R`.
   Ends at `PROVISIONED_PAUSED`; participants see nothing yet. Safe to re-run:
   it re-probes, it never resets state.
3. **Check readiness** — `python -m ridge.deploy status --profile P --runtime R`.
   You want `event_ready: true`, all stages verified.
4. **Distribute team logins** — from `R/inventories/` (private). Each team gets
   its IRIS/CTFd account and its Guacamole desktop connection.
5. **Start the exercise** — `python -m ridge.deploy start --profile P --runtime R`
   → `RUNNING`.
6. **During play** — announcements:
   `python -m ridge.cli announce --operator YOU --text "..."`.
   Free a stuck ticket:
   `python -m ridge.cli recover T03 --generation N --operator YOU --reason "..."`
   (take `N` from `status`; solved answers and points are kept).
7. **Breaks / end of play** — `python -m ridge.deploy pause --profile P --runtime R`.
   The clock freezes; findings and scores persist.
8. **After the AAR, back up** — `python -m ridge.deploy backup --profile P --runtime R`
   → a checksummed recovery set under `R/backups/<timestamp>/`. It is complete
   only when it contains `RECOVERY-COMPLETE.json`.
9. **Shut down** — `python -m ridge.deploy down --profile P --runtime R`
   (data kept). Add `--volumes` only when you mean it: it wipes all event data
   and **refuses unless a verified backup exists**.

Participant URLs (default ports; set `BIND_IP` to the LAN address so participant
laptops can reach them): Guacamole desktops `:8082`, IRIS case `:8081`,
CTFd `:8083`, Wazuh dashboard `:8443` (HTTPS; the shared read-only login is in
the runtime at `secrets/wazuh_reader` — hand it out with the team accounts).
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
| A team disconnects mid-ticket | `status` shows the ticket active with an absent owner | `ridge.cli recover <ticket> --generation N --reason "..."` releases it |
| Desktop sluggish | Host CPU/RAM saturated (`docker stats`) | Pause non-critical team work; stagger Autopsy ingests; do not restart containers mid-event |
| Anything feels lost | Don't improvise | `backup`, then Appendix B |

## Appendix A — Private credentials and backups

- All secrets live only under `R/` (env files, `secrets/`, `inventories/`).
  Retrieve team accounts from `R/inventories/`; bridge credentials from
  `R/secrets/`. None of this is in git.
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
install. Load results and the exact next commands are in
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
