# Silent Ridge: event-readiness handoff

Reviewed 2026-09-16 against merged main **305c257** (PR #12 merged). The original review was read-only. This follow-up publishes the handoff, preserves previously local build recipes, and adds portable native-evidence extraction. No event resources are launched or work scheduled by these files.

## Start here

Moving computers? Read [Continue elsewhere](CONTINUE-ELSEWHERE.md) first. The handoff and preserved build recipes are in this repository; no previous chat or original workstation is required.

1. Read [repository assessment](ASSESSMENT.md).
2. Read [execution contract and sequence](EXECUTION.md).
3. Assign individual files under `tasks/`; each is a self-contained bounded work packet.
4. Track dependencies and completion evidence in `TASKS.md` and `tasks.json`.

5. Use [H01](tasks/H01.md) for the newly identified portable-build consolidation work. It is separate from the original 30 event-readiness tasks.

**Verdict:** the content and transactional core are substantially further along than the top-level documentation suggests. The repository is not yet an event deployment product. The shortest path is a complete two-team vertical slice, then repeatable provisioning, then ten-team validation, then AWS and migration rehearsals. Avoid adding unrelated content or additional services first.

**Open PR recommendations:** refresh and then merge [#6](https://github.com/Judge-M/Oct26/pull/6); defer [#7](https://github.com/Judge-M/Oct26/pull/7) until the existing event is accepted. Neither PR solves a deployment blocker. Both remain untouched.

## Intended user experience

These commands are a **proposed interface, not existing functionality**:

```powershell
# Preparation, before event day; downloads/builds/imports happen here.
.\ridge.ps1 prepare --profile profiles/event-local.json --release vX.Y.Z
.\ridge.ps1 prepare --profile profiles/event-aws.json --release vX.Y.Z

# Event day: one command creates/resumes and verifies the selected deployment.
.\ridge.ps1 up --profile profiles/event-local.json --event ridge-oct26
# Or:
.\ridge.ps1 up --profile profiles/event-aws.json --event ridge-oct26

# Setup leaves the exercise paused. Explicitly add --start to up if desired.
.\ridge.ps1 start --event ridge-oct26
.\ridge.ps1 status --event ridge-oct26
.\ridge.ps1 backup --event ridge-oct26
.\ridge.ps1 switch --event ridge-oct26 --to aws
.\ridge.ps1 down --event ridge-oct26 --retain-backup
```

Linux should expose the same operations through `python -m ridge.deploy`. `up` must be resumable and must never silently reset an existing event. A bootstrap wrapper checks prerequisites and calls the shared Python implementation; it should not duplicate deployment logic in PowerShell.

## Stop point for this request

The review and task plan are the deliverables. Execution of these tasks, PR edits/merges, cloud purchases, and event changes require a subsequent implementation instruction. Future agents should follow the authorization envelope in `EXECUTION.md` rather than repeatedly asking routine design questions.
