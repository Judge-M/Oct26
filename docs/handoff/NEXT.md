# Next bounded work

Read AGENTS.md and BUILD-FIRST.md. This sequence supersedes assumptions about
completion in PRs 14–20. Existing task cards provide the detailed requirements.

## Current position (updated 2026-09-23)

N1–N5 are done (receipts in this directory). **F03 is in progress**: load
tooling merged (PR #43), event-host runbook + dress-rehearsal fixes in PR #44,
interim evidence and remaining steps in [F03-PROGRESS.md](F03-PROGRESS.md).
The only F03 action left is the certifying 10-team/30-session run on event
hardware per `docs/f03-rehearsal.md`. F06 (full dress rehearsal) waits on F03.
AWS track (E03–E05) remains deferred by the organizer until after the local
release is proven.

## N1 — Built central services and automatic two-team identities

Original cards: B01–B04. Inputs: `ridge/deploy/config.py`, `ridge/compose_render.py`,
central/integration Compose files and the two native provisioning adapters.

1. Run the build-first commands on the actual Docker host. Fix any build failure
   before attempting `compose up`. Keep exact build receipts and logs.
2. Wire the validated two-team profile into private bootstrap specs and env files.
   Generate secrets once and preserve them on retries. Discover case, user,
   task-status and CTFd team IDs from returned inventories; never hardcode them.
3. Encode IRIS database initialization (`pgcrypto`) and correct admin-role wiring.
   Start/health-check actual services; validate native schema, account login,
   participant read-only permissions, repeat provisioning and unchanged passwords.
4. Complete Wazuh configuration/certificates/index/roles/views. A null-digest
   candidate manifest cannot satisfy readiness. Test actual queries.
5. Return a sanitized receipt. Do not start the event or advance to AWS.

Done when: a fresh disposable two-team stack and a repeated provisioning run work
without manual SQL, guessed IDs or edited source configuration. Source-only tests
do not complete this task. Carry actual outputs forward to N2.

## N2 — One real desktop through Guacamole, then two teams

Original cards: C01–C03. Use the built container image or the published VM; retain
the other path. Seed the exact prepared case. Apply Guacamole reconciliation to
the actual official schema, verify repeatability and team isolation. Connect three
clients to a shared team desktop. Open the WS17 case and verify BriefSync search;
open the supplied PCAP and Cutter binary. Connect controller evidence publication
to desktops, then verify a newly released file on both desktops and after reconnect.
Do not claim ten-team capacity from this check.

## N3 — Real two-team acceptance and interruption

Original cards: B05, C04, D01. Use `ridge.vertical_slice` against the built stack
with its real configuration and a disposable newly initialized core. Supply
`--state`, `--config`, `--operator`, `--ticket`, `--question`, `--answer`, `--report`
and explicitly `--start`. It must verify native findings/points after delivery,
ownership transfer and persisted state after reopen. Then test actual participant
browser sessions, lost-response delivery and worker restart. Capture the question
matrix results for installed tools. Finish paused.

## N4 — One-command local lifecycle

Only after N1–N3: E01/E02 using `ridge/deploy/`, its frozen profile and journal.
Implement the actual component operations. Test repeated `up`, kill/resume at
each phase, missing-resource re-probes, truthful pause status and refusal to start
when any gate fails. Do not recreate the old `ridge/deploy.py` protocol stub.

## N5 — Recovery, AWS and event acceptance

Only after the appropriate original prerequisites: D02–D04, E03–E05, F01–F06,
G01 and H01. Full restore includes native DBs and every team workspace, not just
SQLite. A verified fresh backup is mandatory before destructive teardown;
`retain-backup` never waives it. Verify resource disappearance/cost inventory.
Fencing must disable source writes before destination activation, including stale
workers. Require independent focused review of restore/deletion/fencing semantics.
Publish a complete versioned offline bundle and run the ten-team rehearsal.

Each task finishes with: revision, files, exact build/run commands and results,
image IDs, sanitized evidence, unresolved blockers, and next task. No auto-merge.
