# N3 Receipt — Real Two-Team Acceptance and Interruption (2026-09-18)

Scope per NEXT.md N3 (cards B05, C04, D01): `ridge.vertical_slice` against the
built N1/N2 stack with its real configuration and a disposable newly initialized
core, explicit `--start`, native findings/points after delivery, ownership
transfer, persisted state after reopen, real participant browser sessions,
lost-response delivery, worker restart, question-matrix results for installed
tools. Finished paused. No ten-team capacity claim.

All secrets stayed in the gitignored runtime directory (`work/n1-run/secrets/`,
`work/n3-run/`); none appear here.

## Gates

- `PYTHONPATH=. python -m unittest discover -s tests` → **Ran 221 tests, OK**
  (includes the vendoring-consistency test for the Wazuh writer role).
- `PYTHONPATH=. python -m ridge.deploy verify-build` → all four receipts match
  the current source fingerprint after rebuilds:
  - iris `sha256:65eb4ba4b807cd039666ed21c8c1c0b8cb471c041257792752b73856b3a38486`
  - ctfd `sha256:3e7e2ce5d4135ebcf1f8a7217950221d485427708aaf3d90ae8aa3c89c7f039e`
  - integration `sha256:c1d365b775c28beff0cef5dddb737dce93257fe2cd65500b56c755f429347036`
  - desktop `sha256:5926732a14d6344b85f2d565e74b7ba8c29e4afeecb38904d05bcae35e2c9f1c`

## Disposable core and slice run

- Fresh `work/n3-run/state.sqlite` initialized from the real N1 identities
  (20 authored tickets; team-01 → IRIS user 3 / CTFd team 1, team-02 → IRIS 4 /
  CTFd 2) and the real slice config (ticket T01, question T01-Q1).
- `ridge.vertical_slice` run with `--state`, `--config`, `--operator`,
  `--ticket`, `--question`, `--answer`, `--report` and explicit `--start`.
- **All phases passed**: preflight → provision → start → claim → answer →
  finding → point → relinquish → takeover → restart. Report:
  `work/n3-run/report-start.json`.
- Native effects verified after delivery: IRIS case 2 carries the claim,
  answer, finding and ownership comments; CTFd holds exactly 1 award
  (team-01, T01-Q1). Ownership transfer team-01 → team-02 recorded with a new
  generation. Persisted state survived close/reopen (restart phase).
- Paused-mode mutation rejection exercised: mutations against the paused core
  are refused; the exercise was left paused (`run.mode = paused`).

## Participant browser sessions (live HTTP, scripted)

21/21 checks passed (`work/n1-run/n3-browser-sessions.py`):

- Real logins: IRIS as team-01 and team-02; CTFd as team-01-p01 / team-02-p01.
- Team identity resolved via the bridge → controller mapping (no hardcoded IDs).
- Mode reported as paused; team-01 score shows 1 (the T01-Q1 award).
- Note: the IRIS session cookie is Secure-marked; over plain HTTP the cookie
  must be replayed as an explicit header. Browser use over HTTPS is unaffected.

## Lost-response delivery (idempotency, live)

- Stopped the integration controller; claimed T02 for team-01 (ownership row
  queued in the outbox); delivered that row manually through the remote sink
  (IRIS comment id 7, no ack recorded); restarted the controller.
- The worker redelivered the same outbox key; the bridge receipt deduplicated
  it: `remote = 7`, no duplicate comment, row `done = 1`, `attempts = 1`.

## Worker restart (live)

- Counts identical before and after a controller restart
  (`work/n3-run/pre-restart-counts.json`): outbox 21 rows / 0 pending,
  IRIS 15 tasks / 5 comments / 5 case-task links, CTFd 1 award.

## Question matrix (installed tools)

- All 14 unique evidence files referenced by the 20 tickets verified present on
  `desktop-team01` under `/evidence`, including the follow-up releases
  (`server/version-comparison.csv` for T09, `hunting/late-inventory.csv` for
  T11) published through `ridge.evidence_release.publish` during the run.
- Wazuh indexer reached 511 documents after the follow-up releases
  (505 → 506 for T07). Reader query `match data.session S-41` → 5 hits.
  (An earlier `term` query against the analyzed field with exact case was a
  query-syntax false alarm in the check itself, not missing data.)
- Tool versions on the desktop: Wireshark 4.2.2, Thunar (file manager),
  Autopsy 4.22.0 (prepared case `WS17.aut`), Cutter 2.5.0. `sensor.pcap`
  contains 24 packets; the training binary is a valid ELF.
- `docs/acceptance/question-matrix.md` was stale: the Autopsy rows still named
  `/evidence/autopsy/WS17/WS17.aut`, which preflight correctly rejects. All
  T03/T04/T05/T08/T13–T16 rows were corrected to the authored evidence and
  source-record paths (verified against the live question records):
  T03 → `/evidence/browser/downloads.csv`, T04 → `/evidence/endpoint/events.csv`,
  T05 → `/evidence/disk/WS17-fat16.img`, T08 → `/evidence/server/access.csv`,
  T13 → `/evidence/prepared/windows-process.json`,
  T14 → `/evidence/prepared/windows-task.json`,
  T15 → `/evidence/prepared/memory-processes.json`,
  T16 → `/evidence/prepared/windows-connections.json`.
  Queries, expected values and limitation text were unchanged.

## Source fixes required by the live run (this PR)

1. **`deployment/expanded/wazuh/roles.json`** — added `indices:admin/get` to
   the writer role. Live probe showed preflight's `GET /<index>` existence
   check needs exactly this grant. Confinement re-verified after the change:
   `/.opendistro_security` → 403, `/_cat/indices` → 403.
2. **`ridge/wazuh_provision.py`** — same grant in `WRITER_ACTIONS` (with
   comment), keeping the generator and the vendored JSON identical; the
   vendoring-consistency test passes again.
3. **`ridge/vertical_slice.py`** — two latent harness bugs that made the slice
   unpassable against the real bridge:
   - answer effects are now measured against a post-claim + drained baseline
     (the old pre-start baseline counted the claim's own effects as answer
     effects);
   - the restart check now compares against the settled effect set captured
     after the takeover drain, not the pre-restart intermediate set.
4. **`deployment/expanded/compose.integration.yaml`** — joined the integration
   service to the external `wazuh-backend` network (`${RIDGE_WAZUH_NETWORK}`)
   in addition to `central`. Without it the controller could not reach the
   indexer for CSV telemetry on evidence releases — a real gap, found live.

## Docs

- `docs/acceptance/question-matrix.md` — stale Autopsy paths corrected (above).
- `docs/handoff/ASSESSMENT.md` — dated status note added: P0 items 1–5 are
  addressed by N1–N3; item 6 (ten-team capacity) remains open.

## Operational notes

- State reset method (used once after a consumed fresh core; documented, not
  needed for normal operation): delete generated IRIS tasks/comments via the
  IRIS ORM inside the container, and delete `Silent Ridge` `RidgeCredit`/
  awards via the CTFd app context. UI/CSRF deletion was a dead end (rotating
  CSRF seed, Secure cookie).
- The integration image was rebuilt with the `vertical_slice.py` fix before
  the acceptance run; all four images were rebuilt again afterward so
  `verify-build` receipts match the final source.

## Unresolved / carried forward

- No ten-team capacity claim (P0 item 6 open).
- GUI walkthrough of the participant desktop session (visual pass through
  Guacamole) still owed; N2/N3 verified protocol-level sessions and tooling.
- N4 next: one-command local lifecycle via `ridge/deploy/` (E01/E02) — repeated
  `up`, kill/resume at each phase, missing-resource re-probes, truthful pause
  status, refusal to start when any gate fails.

## Final state

- Exercise **paused** (`run.mode = paused`); outbox 21/21 done, 0 pending.
- Integration controller container healthy; central, Wazuh, Guacamole and both
  desktops left running for inspection.
