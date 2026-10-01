# Silent Ridge: event-readiness handoff

Reviewed 2026-09-16 against merged main **305c257** (PR #12 merged). The original review was read-only. This follow-up publishes the handoff, preserves previously local build recipes, and adds portable native-evidence extraction. No event resources are launched or work scheduled by these files.

## Current integration entry point

Read [Consolidation](CONSOLIDATION.md), [Build first](BUILD-FIRST.md), and
[Next bounded work](NEXT.md). Give a new agent [this starter prompt](STARTER-PROMPT.md).
The dated assessment below is historical; source additions do not complete live gates.

## Latest: walkthrough review (2026-10-01)

[Handoff](WALKTHROUGH-REVIEW.md) and [full review](../reviews/walkthrough-review-2026-10-01.md)
— an independent content review of `docs/walkthrough/CTF-WALKTHROUGH.md` (PR #196,
`dd46a18`), with every claim re-derived from the repository. **14 findings: 7
contradict a source of truth, 4 are internal inconsistencies, 2 are unverified claims,
1 is a PR-structure problem.** The largest is section 7's phase tables: boundaries are
shifted by one ticket from T11 on, and 5 of 20 tool entries are wrong. Two findings are
not prose fixes — `silent-ridge-timed`/`-timeless` are both titled `silent-ridge-*` so
neither is selectable by the name the document uses, and the "verbatim" coached route
quotes content that exists only on PR #192's branch. **Fixes not applied**; five
decisions are waiting on the organizer. Nothing here certifies the event: no human has
played.

## Latest: 5-team AI stress test (2026-09-30)

[Stress report](STRESS-5TEAM-REPORT.md) and
[metrics](STRESS-5TEAM-METRICS.md) — five AI teams played the full exercise
concurrently and **completed it: 80/80 questions, 20/20 tickets, 80 IRIS
findings, 80 CTFd awards, outbox 100% drained.** The serving layer was never the
bottleneck: p95 under 50 ms, zero non-2xx across 444 probes, 4.77 GiB peak
across 19 containers, 67.5% host reserve. Every problem was in the participant
write path or content design. Two teams scored zero and both concluded the
product was broken — in both cases the first diagnosis was wrong, and the cause
was partly the test harness. **No human has played**; the desktop-usability
gate is still open. Corrects an earlier claim: the host has 63.7 GiB RAM, not
31.7, so ten teams is limited by the Docker memory cap rather than the hardware.

## Latest: content audit, all 80 taught paths (2026-09-30)

[Content audit receipt](CONTENT-AUDIT-RECEIPT.md) — every question's taught
investigation route checked against the evidence actually released to
participants. **77 of 80 are sound; 3 point at a file that does not contain
their answer** (T01-Q1, T07-Q2, T07-Q4), and 3 more need an author's judgement.
Every answer was digest-verified before use, so these are provably the intended
answers. Six of 80 questions now carry route supplements; all 80 answers are
unchanged. Includes three self-corrections, all measurement errors of mine that
first looked like product defects: an over-report of 11 broken questions caused by
byte-grepping length-prefixed DNS names, then by converting `10.26.10.17` to the
wrong hex — **T02 is sound** and a proper Ethernet/IPv4/UDP/DNS decode shows all
four answers in `dns.pcap` where the ticket says — and finally T12-Q2/Q3, which I
escalated as unfixable but which `server/collection.txt` states as
`09:14–09:18` in text my exact-substring search missed. Live 5-team play then
found a fourth class the static audit could not detect by construction: T07-Q1's
answer is in the named file but not surfaced by the ticket's stated selection.

## Latest: desktop usability pass (2026-09-30)

[Desktop usability receipt](DESKTOP-USABILITY-RECEIPT.md) — the N2/F03 gate,
partially closed. Verified **inside** the running team desktop: Xfce and
TigerVNC up, the real WS17 case seeded, Wireshark 4.2.2 / Firefox 140.16 /
Cutter / Autopsy all runnable, and all 45 Sleuthkit native libraries resolving.
Completed a full VncAuth handshake through the Guacamole-provisioned password
and got a real 1440x900 framebuffer, while the *other* team's password was
rejected — so team isolation holds at the VNC layer, not just in the database.
Found one real content defect: **T01-Q1's taught evidence path does not reach
its own answer**, because `WS-17` appears nowhere in the `sensor.pcap` the
ticket sends you to. No human has yet investigated a ticket, so the gate is
still open for actual usability.

## Latest: clean-baseline reproduction (2026-09-29)

[Clean-baseline receipt](CLEAN-BASELINE-RECEIPT.md) — fresh clone on a cleaned
Windows host, baseline `4203239`. LFS, case template, all four images and
`verify-build` pass; 395 tests green. It documents one real defect found and fixed
(`bounded_http` returned a TCP reset instead of a 503 for a rejected connection on
Windows, now covered by a regression test) and one failure that was host
contamination rather than a repository bug (a `ubuntu:24.04` base tag overwritten
by a previous build). No event was started and no readiness is claimed.

## Latest: full-system verification, all 80 questions (2026-09-30)

[Full-verification receipt](FULL-VERIFICATION-RECEIPT.md) — all 80 questions
answered, 0 wrong, 20/20 tickets closed, and the effects read back from the
native stores: 80 finding comments and 20 closed tasks in IRIS's own database,
80 `Awards` rows correctly attributed to team-01 in CTFd, outbox drained. Load
check: 2 teams x 3 sessions, 0 failures on all 9 endpoints. **Not event
certification** — every session was scripted HTTP, so the desktop-usability gate
(N2/F03) is still open, and no restart, redelivery, takeover or backup/restore
test was performed. Also records that `expanded/tickets.json` is gitignored and
absent, so the documented walkthrough cannot run on a clean clone.

## Latest: two-team pilot bring-up (2026-09-29)

[Pilot receipt](PILOT-2TEAM-RECEIPT.md) — first successful local bring-up on a
cleanly rebuilt host. `PROVISIONED_PAUSED` with all seven stages verified, 2
teams, 505 evidence documents, 20 tickets. Four real defects were fixed on the
way, all invisible to the unit suite: two Wazuh certificate-filename mismatches
that crash-looped the indexer and dashboard, a service rename that broke the
indexer DNS name, and a hardcoded `127.0.0.1` that made `up` fail on any host
bound to a LAN address. **Paused, not started** — no participant session, ticket
claim, answer or point is claimed. Also records that a source build cannot
obtain the upstream Wazuh config without the release bundle.

## Latest: clean-baseline reproduction (2026-09-29)

[Clean-baseline receipt](CLEAN-BASELINE-RECEIPT.md) — fresh clone on a cleaned
Windows host, baseline `4203239`. LFS, case template, all four images and
`verify-build` pass; 395 tests green. It documents one real defect found and fixed
(`bounded_http` returned a TCP reset instead of a 503 for a rejected connection on
Windows, now covered by a regression test) and one failure that was host
contamination rather than a repository bug (a `ubuntu:24.04` base tag overwritten
by a previous build). No event was started and no readiness is claimed.

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
