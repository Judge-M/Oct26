# Next bounded work

Read AGENTS.md and BUILD-FIRST.md. This sequence supersedes assumptions about
completion in PRs 14–20. Existing task cards provide the detailed requirements.

## Current position (updated 2026-09-24)

N1–N5 are done (receipts in this directory). **F03 is in progress**: load
tooling merged (PR #43), runbook + dress-rehearsal fixes + `--teams N`
switch merged (PRs #44/#45), capacity model retuned from measurements
(PR #46), event-day command sheet at `docs/event-day-commands.md`
(PR #47); interim evidence and remaining steps in [F03-PROGRESS.md](F03-PROGRESS.md).
The only F03 action left is the certifying 10-team/30-session run on event
hardware per `docs/f03-rehearsal.md`. F06 (full dress rehearsal) waits on F03.
AWS track (E03–E05) remains deferred by the organizer until after the local
release is proven.

External code review fixes: a review of `e3e6060` found three
teardown/fencing defects (fence missing from CLI dispatch; `down
--volumes` accepted stale backups; a refused wipe still stopped the
event). All three fixed with five regression tests on PR #49 — merge
before the dress rehearsal and before relying on event-day teardown.

Participant-facing material: event-day briefing deck at
`docs/event-day-deck/` (13 slides — narrative + click-by-click setup,
validated with `kimi-slides check` and full-page screenshots; projectable
`event-day-deck.pdf` committed alongside the `.pptd` source; PR #48).

Cold-reader pass (2026-09-24, PR #48): found and fixed three host-path
gaps — (1) the offline bundle never shipped the release vault
(`work/release/controller/releases`), so a cold bundle install would pass
preflight but fail the first follow-up ticket mid-event;
`scripts/assemble_offline_store.py` now packs
`dependencies/release-vault.tar.gz` (v0.9.0-drill predates it — the
command sheet carries the workaround); (2) `docs/event-day-commands.md`
step 0/2 now gives exact bundle extraction commands and `assets/…` paths
for `local.json`, and states plainly that source builds produce images
only; (3) the README reframes the bundle as the host path and source
builds as the developer path. Remaining honesty note: the bundle →
extract → `up` flow itself has not yet been run cold on a second machine —
that is part of the F06 dress rehearsal on event hardware.

Bundle reassembly (2026-09-24, PR #51): rebuilt all four custom images on
current source, assembled a new rehearsal bundle at
`work/offline-bundle-v010` (13 GB; the parked QCOW2 is now excluded by
default — `--include-vm` opts back in). The release vault is packed
(`dependencies/release-vault.tar.gz`). Dry-run install passes: all hashes
verified, source extracted, receipt written, all 13 manifest image IDs
present in the daemon. **Found and fixed a fourth cold-host defect in the
process**: `ridge.bundle` saved images by bare sha256 ID, which strips
RepoTags — a truly cold `docker load` yields untagged `<none>` images and
every compose file fails (`pull_policy: never`). The 2026-09-21 drill
cold test masked it because that machine already had the tags.
`ridge.bundle` now saves by manifest `image_tags` (verified to resolve to
the pinned IDs) and `ridge.offline_install` verifies tags after load
(`tags_verified` in the receipt); 5 new tests, 304/304 pass. The new
bundle's image tar was opened and all 13 RepoTags confirmed present.
`docker load` of the full 5.7 GiB tar exceeds this machine's 5-minute
tool cap, so an end-to-end load was not re-run here — it is covered by
the drill test's proven load path plus the new tag-content check, and the
real load runs on event hardware in Phase 0 of
`docs/dress-rehearsal-plan.md`. **Note: `v0.9.0-drill`'s image tar is
tagless — treat it as superseded; the next published release must come
from this branch's tooling.**

Rehearsal session plan: `docs/dress-rehearsal-plan.md` sequences the
event-hardware day end-to-end — bundle reassembly (must include the
release vault; `v0.9.0-drill` predates it), timed cold install, F03
certifying run, F06 functional rehearsal + lost-host recovery drill, and
the release freeze, with go/no-go gates per phase. Requires PR #49
(teardown/fencing fixes) merged first — the drill exercises those
semantics.

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
