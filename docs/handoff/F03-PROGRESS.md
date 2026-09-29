# F03 Progress Note (interim — task NOT complete)

Date: 2026-09-23. Branches/PRs: `f03/load-tooling` (PR #43, merged),
`f03/rehearsal-runbook` (PR #44). Test count: **295 passing**.

This is an interim handoff note, not the F03 receipt. The certifying run
on event-capable hardware is still outstanding; nothing here certifies
capacity.

## What exists now

- `expanded/load.py` — capacity rehearsal harness. Drives the real
  participant surface (CTFd login → `/silent-ridge` queue → status poll →
  scoreboard → coached-question answers with the wrong-on-purpose probe
  answer `load-test-probe`; IRIS login/dashboard/case per team), samples
  `docker stats` per container and integration outbox depth, and emits
  JSON + Markdown reports with latency percentiles, container peaks, and
  host reserve. Reports self-label `NON-CERTIFYING` unless the run matches
  the declared event profile (teams, sessions, min host RAM), per the F03
  card's do-not-certify-from-the-dev-box rule.
- `tests/test_load.py` — 11 tests with a fake CTFd covering login, nonce
  forms, the answer write path, and CSRF enforcement.
- `docs/f03-rehearsal.md` — event-host runbook: acceptance targets, config
  template, exact commands, manual desktop usability pass, known traps.
- `ridge deploy up --teams N` (1–10) — start-time team-count switch with
  neutral accounts, persisted in `runtime/overrides.json` so later
  lifecycle commands see the same roster and journal fingerprint without
  repeating the flag; profile capacity validation still applies.
- Sanitized evidence: [2-team smoke on restored stack](evidence/f03/smoke-2team-restored-stack.md),
  [2-team dress rehearsal on fresh stack](evidence/f03/dress-2team-fresh-stack.md).

## Defects found and fixed during the dress rehearsal

1. Fresh `up` failed: the three external networks (`<event>-central`,
   `<event>-desktop`, `<event>-wazuh_wazuh-backend`) were never created.
   `_ensure_networks()` in `ridge/deploy/local.py` now creates them
   idempotently in the infrastructure stage.
2. Evidence probe could never pass: `telemetry.jsonl` has 508 lines with 3
   duplicates; the indexer dedupes by content hash (505 documents). The
   probe now expects the unique-record count.
3. `expanded/load.py` read a stale credentials shape; current runtimes
   produce `teams.<team>.accounts` + `iris_login`/`iris_password`.

## Operational lessons (encoded in the runbook)

- `up` is an idempotent reconcile — re-run until all stages verify. The
  guacd image healthcheck fires only every 300 s, so first boot needs
  patience, not fixes.
- The `wazuh_config` asset embeds the hashed admin password; a runtime's
  `secrets/wazuh_admin` must be the matching generation or the indexer
  job gets HTTP 401.
- Never open the live `state.sqlite` from the host over Docker Desktop
  bind mounts — the reader stalls the in-container writer (observed as
  141/148 503s on `/silent-ridge`). The harness byte-copies first.

## Measured so far (non-certifying, 20 GiB dev host)

- 2-team fresh stack, 180 s, 6 CTFd + 2 IRIS sessions: 473/473 requests
  OK, p95 ≤ 0.14 s on all endpoints, outbox flat at 15, peak working set
  6.4 GiB across all containers.
- Per-container peaks (fresh stack): iris-worker 2.5 GiB, wazuh-indexer
  1.9 GiB, desktops ~1.6 GiB, everything else ≤ 0.75 GiB.

## Capacity model retune (2026-09-23)

Validation now uses measured reservations instead of the original
placeholder 8 GiB / 4 vCPU per desktop: central 6 GiB, desktop
2 GiB / 1 vCPU / 15 GiB, plus a 20% memory headroom factor in
`_check_capacity`. Consequence: a 32 GiB / 16-core host validates for
`--teams 10`, matching the README's stated minimum. The AWS example
profile's desktop VM was resized to 4 GiB (t3.medium class). These are
measured *peaks with margin*, and the certifying run should confirm or
adjust them — the check is not weakened, just realistic.

Related participant-experience change: all web apps (IRIS :8081,
CTFd :8083, Wazuh :8443, Guacamole :8082) are now documented as
own-laptop-browser destinations; the remote desktop is for native tools
only (Autopsy 32/80 questions, Wireshark 8, Cutter 8, file manager 8 —
the 24 Wazuh questions no longer require an in-desktop Firefox). This
keeps ~1 GiB of browser RAM per desktop out of the capacity budget.


## Known limitations / what remains for F03

- Certifying run on the event host: 10 teams × 30 sessions, ≥ 30 min,
  per `docs/f03-rehearsal.md`. Must include the manual desktop usability
  pass (Kasm/Guacamole interactivity is not measured by the harness).
- Live answer-write path needs a claimed IRIS ticket; the dress run
  exercised reads only (answer POST is covered by unit tests).
- F06 (full event dress rehearsal/recovery drill on event hardware) is a
  separate, still-open card; the 2-team dev-box walkthrough above is only
  a partial rehearsal and does not satisfy it.

## Next task now unblocked

- Event-host F03 run (runbook ready; fill in host IP/RAM and go).
- After F03 + F05: F06 full dress rehearsal.
