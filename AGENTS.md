# Instructions for coding agents

## Product and source of truth

Build a complete incident-response CTF for ten teams / thirty participants. All
fictional content, published native evidence, prepared cases, images, manifests,
build recipes and instructions belong on GitHub. Credentials, real rosters and
live event state do not. A fresh computer must not need an earlier chat or an
original developer's files. Preserve the published VM as the accepted artifact;
the container desktop is an additional path until its live gates pass.

Read these small files in order before choosing work:

1. `docs/handoff/CONSOLIDATION.md` — what was retained and deferred from old PRs.
2. `docs/handoff/BUILD-FIRST.md` — actual preparation/build/run commands.
3. `docs/handoff/NEXT.md` — next bounded task and the required evidence.
4. The selected task card and `docs/handoff/EXECUTION.md`.

These instructions override stale host-specific statements in old task reports.
Measure the current host; do not assume Docker, a hypervisor or credentials are
missing because another agent said so. Distinguish CLI availability, daemon
availability, image availability and an actually running healthy application.

## Work one dependency at a time

- Select exactly one task. Finish its implementation, required build and checks
  before advancing. Do not implement later waves against invented interfaces.
- The shared deployment package is `ridge/deploy/`. Never add `ridge/deploy.py`.
  Reuse `ridge.deploy.config` and the SQLite journal. Interface changes update
  all consumers and tests together.
- The next milestone is a real two-team local vertical slice. AWS, switching,
  destructive teardown and full recovery stay blocked until their prerequisites
  pass. A protocol, command list, fake provider or boolean is not an implementation.
- Prefer one small commit per task on the integration branch. Do not resurrect
  superseded PRs or merge unrelated branches. Leave landing to the organizer.

## Build before run — mandatory

1. Inspect the current environment and exact checked-out revision.
2. Fetch required Git LFS bytes and verify their manifests.
3. Read the real build recipe. Run the build and wait for successful completion.
4. Verify the resulting image ID and current build inputs.
5. Only then run containers, migrations, provisioning and runtime tests.
6. A failed build blocks runtime work. Fix the build; do not substitute a stub,
   skip the failing layer, weaken a checksum or claim a syntax check built it.

`docker compose config`, `docker build --check`, unit tests, and image URL
reachability are useful but none proves an image exists or starts. Run
`python -m ridge.deploy build` followed by `verify-build`; see BUILD-FIRST.md.
Never try to run the proposed event-day commands as though the complete event
orchestrator already exists. Its CLI deliberately reports the missing gate.

## Safety and correctness invariants

- Setup remains paused. Never report pause without observing it in the core.
- Repeated setup preserves identities, scores, findings and participant work.
- Verify remote effects after delivery; HTTP success or a local outbox row alone
  does not prove an IRIS finding or CTFd point exists.
- Do not claim recovery after restoring only SQLite. All native databases,
  receipts, evidence state, secrets and team workspaces must be restored and checked.
- A local lock is not cross-site fencing. Never activate a second site on an
  operator flag alone or permit stale workers to keep writing.
- Do not publish secrets or real event backups. Use generated disposable test
  secrets and private files. Never print them in CI or chat.
- Do not overwrite published evidence to make a test pass. Historical incident
  timestamps stay historical; native acquisition uses actual acquisition UTC.
  T16 is a live connection snapshot, not validated memory connection evidence.
- No cloud spending, public exposure, host reconfiguration or destructive cleanup
  outside the organizer's explicit envelope. Routine source fixes and isolated
  builds/tests need no repeated permission. Clean only exact resources owned by
  the current disposable test; never run a global prune or delete event volumes.

## Evidence and completion

For each task record: commit, changed files, build commands, exit codes, image
IDs/checksums, exact tests and results, log locations, limitations, next unblocked
task. Keep sanitized summaries in the repo; private receipts live under `work/`.
Use distinct statuses: source implemented, image built, service started, live
acceptance passed, event-ready. Do not collapse these into “done.”

Run `python -m unittest discover -s tests` and the relevant actual image smoke.
When blocked, record the exact failing command and error, complete independent
work within this task, then stop at the dependency boundary. Do not leap ahead
to AWS or manufacture evidence. Never mark `event_ready` from unit tests alone.
