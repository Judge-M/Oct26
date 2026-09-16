# Execution contract for future agents

## Defaults that avoid repeated design questions

- Support ten teams / thirty participants, normally three people sharing each team desktop. Keep one global ticket owner and durable shared findings.
- Local Windows entrypoint targets Hyper-V for event VMs, with a Linux central-services guest; reuse WSL/QEMU for preparation and small development rehearsals. A remote Linux/KVM profile can reuse the same provider contract. Do not run ten desktops on this 32-GiB host without measured capacity.
- AWS starts with ordinary EC2: one measured central-services host and one desktop per team, private desktop/service ports, an authenticated gateway, no Kubernetes/RDS requirement. These are design defaults to validate, not sized purchases.
- One coherent active site. Start with planned pause/backup/restore switching and cold standby; add faster failover only after measured recovery requires it. Pre-import images before the event.
- Public GitHub holds code, fictional answers/content, disk parts, case/native archives, manifests and guides. Private runtime storage holds credentials, roster data, live databases, exports and backups.
- Use immutable release IDs, real checksums and measured acceptance. Do not turn `compatibility_verified` or `event_ready` on merely because files exist or unit tests pass.

## Small unavoidable organizer decisions — collect once

Future implementation should collect one private profile, not ask these repeatedly:

1. Event date, time zone, duration, location/network and whether four hours of active investigation is required. The scenario date is not automatically the event date.
2. Available local host inventory, administrator access and permission for the designated VM/network locations. Establish whether sufficient event hardware will be supplied or AWS is primary.
3. If using AWS: account/region, authorized role/profile, spending cap, allowed maximum live duration, allowed retained backup/image storage and ingress CIDRs/access method. Do not request access keys in chat.
4. Roster or authorization to generate neutral participant accounts and a private credential handout.
5. Backup destination, retention, desired recovery point/time and whether a warm standby's recurring cost is acceptable.

Unanswered sizing questions should not block source work: implement dry-run profiles and two-team tests. They must block costly deployment or a misleading capacity approval. AWS budget alerts are not a hard spending cutoff; implement TTL teardown and verify remaining inventory as separate controls.

## Agent assignment rules

- Assign exactly one task card at a time, plus this contract. Read only its listed files and dependencies first. Consult broader code only for a specific unresolved symbol or contract.
- Use one branch/worktree per task. A coordinator owns interfaces and dependency order. Do not let concurrent agents edit the same shared schema/CLI file.
- Most documentation, configuration, packaging and adapter tasks suit a smaller model with deterministic tests. Tasks involving transaction semantics, fencing, restore and deletion need an additional focused reviewer; this can be another agent, not necessarily the user.
- No task may quietly solve unrelated tasks, weaken checks, catch-and-ignore failed provisioning, use placeholder artifact bytes, or replace a failed acceptance check with a stub.
- Source work, tests, generation of fictional content and draft PRs can proceed under an implementation authorization. Cloud spending, public exposure, privileged host changes and deletion must stay within the organizer's one-time explicit envelope. Routine retries inside it need no repeated question.
- Never merge to bypass failed CI. If merge authority is absent, prepare a ready PR and let the coordinator handle landing under the user's existing policy.
- Freeze shared contracts after tasks A03/A04; changes require a short compatibility note and updates to downstream consumers/tests in a coordinated task.

## Standard task output

Each agent returns a compact receipt:

```text
Task ID / branch / commit:
Files changed:
Contract implemented:
Checks run and exact result:
Evidence files / release identifiers:
Known limitations:
Next task now unblocked:
```

Save machine-readable evidence under a run-specific private `work/acceptance/<id>/` when it contains credentials, account IDs or participant data. Publish only sanitized acceptance summaries. Failure output names the component, safe diagnostic, retry action and whether changes were committed. Never print credentials in logs.

## Scheduling / dependency waves

| Wave | Tasks | Gate to advance |
|---|---|---|
| 0 | A01–A05 | Current facts reconciled; path, config and lifecycle contracts fixed |
| 1 | B01–B05, C01 | Central services + two configured desktops ready while paused |
| 2 | C02–C04, D01 | Real accounts can claim, solve and receive newly released evidence |
| 3 | D02–D04, E01–E02 | Full live fault/restore checks and one-command local setup pass |
| 4 | E03–E05, F01–F02 | AWS image/deployment/teardown and fenced switching work |
| 5 | F03–F06, G01 | Ten-team capacity, adequate learning time, cold offline install, recovery rehearsal |

Tasks may run independently only after their listed dependencies pass. Example parallel lanes: B01/B02 adapter provisioning; B03 Wazuh; C01 desktop conversion. Serialize shared Compose/CLI edits through B04/E01. Maximum sensible concurrent agents: 2–3, not one per card. Do not run expensive integration stacks simultaneously on a memory-constrained host.

## Proposed deployment state machine

`NEW → ARTIFACTS_VERIFIED → INFRASTRUCTURE_READY → APPLICATIONS_READY → IDENTITIES_READY → DESKTOPS_READY → EVIDENCE_READY → PROVISIONED_PAUSED → RUNNING → PAUSED → BACKUP_VERIFIED → STOPPED/DESTROYED`

Store event ID, deployment ID, provider resource IDs, release/manifest digest, completed step receipts, configuration fingerprint, backup references and active-site generation in a private journal outside disposable instances. Lock per event. Probe before mutating; record a step only after verifying its effect. Recovery never treats a half-written directory or an accepted API request as successful deployment. Poll bounded jobs with backoff; retries resume known resource IDs.

`up` prepares and checks everything, then leaves the exercise paused unless `--start` was explicitly supplied. Provisioning can drain initial tasks while paused; participant claims/answers must remain rejected. `down` does not mean “delete everything”: it verifies a restorable backup, removes owned compute/network resources, and reports deliberately retained storage and estimated ongoing cost. A separate explicit purge operation may remove retained backups under policy.

## Planned cross-provider switch

1. Verify destination artifact availability and capacity before interrupting the source.
2. Pause, drain outbox, freeze native edits and team workspace writes.
3. Produce a coherent, encrypted recovery set; validate checksums and restore metadata.
4. Fence source mutation and increment active-site generation using an authority that is not the source's disposable local database alone.
5. Restore application DBs, receipts, IDs, core, evidence state, Wazuh, Guacamole and team workspaces at destination.
6. Rebind provider-specific addresses/secrets without rewriting historical evidence or receipts; verify equality of scores, findings and ownership.
7. Run participant and controller smoke checks while paused; change the entrypoint and resume only after fencing/health pass.
8. Retain a rollback checkpoint. Never unpause both sides. If source is unreachable, require a proven fencing method and use the latest completed backup; report the actual recovery point and possible lost work.

## Release/event approval gates

No release is event-ready until all are evidenced against the same immutable version:

- Blank-host setup and repeat `up` succeed; interrupted setup resumes with unchanged identities and scores.
- All 80 existing questions are reachable and answerable on installed tools; any added curriculum has the same coverage.
- No participant mutation before start or while paused; no unauthorized team/admin routes.
- Live IRIS/CTFd lost-response/restart tests yield one award/finding/task effect per event key.
- Follow-up files and Wazuh records become usable on every required desktop, including reconnecting clients.
- Three simultaneous clients per team behave as intended; 30-client/ten-team load has measured headroom and bounded latency.
- A full backup restores onto a clean destination with no missing case/workspace work; switching fences the old writer.
- Offline local setup needs no Internet, package manager, symbol service or remote authentication.
- AWS teardown leaves only explicitly retained and reported resources; an interrupted setup is also cleanable.
- Duration/learning goals have evidence beyond arithmetic and scripted answer submission.

## Suggested calendar, relative to event day

T−28 to T−21: contracts and two-team vertical slice. T−21 to T−14: repeatable setup, fault testing, full backup/restore. T−14 to T−10: AWS import, teardown and cross-provider drill. T−10 to T−7: ten-team performance and beginner learning rehearsal. T−7: freeze release and mirrored offline cache. T−3: cold installation rehearsal and alternate-site recovery. T−1: verify capacity, credentials, clocks and backups; no feature changes. Event day: one setup command, health check, explicit start, monitored backups, AAR export, verified teardown.

These are sequencing targets, not promised durations. If less calendar time remains, defer optional curriculum imports and cosmetic work; do not waive recovery, capacity or access gates.
