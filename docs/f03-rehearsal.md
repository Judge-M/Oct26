# F03 capacity rehearsal — event-host runbook

One-page procedure for the certifying ten-team / thirty-session load run.
The harness is `expanded/load.py` (see `tests/test_load.py` for the mocked
flow). A run only counts as certification when the report says
`CERTIFYING`; anything smaller is automatically labeled a non-certifying
smoke run.

## Acceptance targets (from docs/handoff/tasks/F03.md)

- p95 ordinary app requests < 2 s
- score/finding delivery < 10 s (outbox drains, no steady growth)
- no OOM / swap collapse
- ≥ 20% measured RAM reserve at peak
- desktop usability spot-check passes while the run is active

## Host

- Event-capable machine, ≥ 32 GiB RAM (the dev box does **not** certify)
- Docker Desktop / Docker Engine running, images already built
  (`python -m ridge.deploy build --component all` +
  `python -m ridge.deploy verify-build`)

## Procedure

1. Bring the event stack up (paused) with the ten-desktop profile:

   ```bash
   python -m ridge.deploy up --profile <profile.json> --runtime <runtime-dir>
   ```

2. Create `f03-config.json` (paths relative to the repo root; omit
   `containers` to sample every running container):

   ```json
   {
     "teams": 10,
     "sessions_per_team": 3,
     "ctfd_url": "http://127.0.0.1:8083",
     "iris_url": "http://127.0.0.1:8081",
     "credentials": "<runtime-dir>/secrets/team-credentials.json",
     "state_sqlite": "<runtime-dir>/state/state.sqlite",
     "host": {"ram_gib": 32},
     "event_profile": {"teams": 10, "sessions_per_team": 3, "min_host_ram_gib": 32}
   }
   ```

   Set `host.ram_gib` to the machine's actual RAM.

3. Start the exercise, then run the harness (1800 s = 30 minutes; runs
   under 30 s are refused; use a fresh output directory every time):

   ```bash
   python -m ridge.deploy start --profile <profile.json> --runtime <runtime-dir>
   PYTHONPATH=. python -m expanded.load --config f03-config.json --duration 1800 --output work/f03/event-run
   ```

4. While it runs, do the desktop usability pass by hand: open two or three
   team desktops through Guacamole (`http://<host>:8082`), launch Autopsy,
   open the prepared case, run a search — note any lag or freeze. The
   harness does not measure desktop interactivity.

5. Read `work/f03/event-run/report.md`. Check:
   - `CERTIFYING` label present
   - zero or near-zero failures per endpoint; p95 within target
   - outbox depth min/max flat or draining, not climbing
   - peak working set ≤ 80% of host RAM

6. Publish the sanitized report (it contains no credentials — verify
   before publishing) as the F03 evidence.

## Notes and known traps

- The stock CTFd challenge API is deliberately closed to participants;
  the harness drives `/silent-ridge`, which is the real flow.
- Never let other tools open the live `state.sqlite` from the host while
  the stack runs — SQLite locks do not cross Docker Desktop bind mounts
  and a host reader stalls the integration writer (observed as 503s on
  `/silent-ridge`). The harness byte-copies before reading; keep it that
  way.
- Answer POSTs use the wrong-on-purpose answer `load-test-probe`; a
  rehearsal never earns points. If a run happens while questions are
  already answered (e.g. a restored drill state), the answer path is
  simply not exercised — say so in the evidence.
