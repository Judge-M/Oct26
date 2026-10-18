# Completed 80-question rehearsal rerun

Date: 2026-10-18  
Event: `ridge-oct26-rerun`  
Release: `b6252ad` (`rehearsal-20261018`)  
Participant hostname: `desktop-t5pf26o.tail799fee.ts.net`  
Browser policy: isolated in-app browser; the user's logged-in Chrome was not used.

## Verified outcome

This was a real end-to-end rehearsal against a fresh event profile. Ten team
identities worked the participant surfaces and the facilitator/admin role was
validated through the controller CLI. The event reached the intended shared
end state:

| Check | Result |
|---|---:|
| Ticket stages complete | 20 / 20 |
| Accepted answers | 80 / 80 |
| Team scores | 10 teams × 8 points |
| Pending delivery queue | 0 |
| Active leases | 0 |
| Controller mode | running |
| Diagnostic failures | 0 |

The authoritative verification was performed inside the integration container
with the event state database, followed by `ridge.cli status` and
`ridge.cli diagnostics`. The browser displayed the final “Exercise complete”
state and “Shared progress: 20 of 20 ticket stages complete.”

## Team-to-ticket execution map

The logical teams were serialized through the isolated browser so one shared
browser cookie jar could not cross-contaminate identities. The mapping below
records who completed each stage:

| Team | Completed stages |
|---|---|
| Team 1 | T01, T11 |
| Team 2 | T02, T12 |
| Team 3 | T03, T13 |
| Team 4 | T04, T14 |
| Team 5 | T05, T15 |
| Team 6 | T06, T16 |
| Team 7 | T07, T17 |
| Team 8 | T08, T18 |
| Team 9 | T09, T19 |
| Team 10 | T10, T20 |

Every question was answered through the CTFd form after its IRIS ticket was
claimed. Each answer was checked in the UI, and the named evidence limitation
was preserved in the published finding.

## Question-by-question walkthrough

The values below are the accepted values and the human-readable reason for
each one. The question cards also display the evidence source and limitation;
the run used those named sources rather than bypassing the participant flow.

| Ticket | Accepted answers, Q1 → Q4 | Human explanation |
|---|---|---|
| T01 | `WS-17`; `req-71`; `req-72`; `198.51.100.77` | Correlate the plan request and upload in the sensor capture; the traffic identifies the workstation, request IDs, and destination, but not human receipt or intent. |
| T02 | `relay.archive.example`; `198.51.100.77`; `WS-17/10.26.10.17`; `60` | Resolve the recorded name and compare the DNS client, answer address, and TTL. |
| T03 | `08:57:00`; `brief-viewer.exe`; `briefs.helpdesk.example`; `C:/Downloads` | Read the browser download export and preserve its UTC normalization and target path. |
| T04 | `BriefSync`; `brief-viewer.exe`; `user logon`; `09:08:00` | Inspect the task-registration event, then apply the documented 120-second WS-17 clock correction once. |
| T05 | `LANTERN`; `3`; `AMBER`; `CEDAR` | Recover the deleted cache entry and transcribe the patrol, version, sector, and check-in word. |
| T06 | `m.ellis`; `09:03:00`; `previous_claim`; `no` | Separate the successful session refresh from the separate failed password login. |
| T07 | `09:20:00`; `09:26:00`; `S-41`; `session revocation` | Compare the reset and late refresh records; an active session requires explicit revocation for containment. |
| T08 | `plan-v3`; `403`; `0`; `req-75` | Read the access export: the plan download succeeded, while the roster request was denied with an empty body. |
| T09 | `09:10:00`; `BLUE`; `10:30-11:30Z`; `CEDAR` | Compare the released v4 record to v3; the sector and window changed but the check-in word did not. |
| T10 | `WS-22`; `Exercise IT`; `C:/Program Files/Approved/briefsync.exe`; `r.chen` | Use the benign comparator to distinguish an approved similarly named task from the incident lead. |
| T11 | `BriefSync`; `08:45:00`; `08:50:00`; `no` | The WS-31 inventory shows a task, but collection stopped before execution could be established. |
| T12 | `WS-31`; `09:14:00`; `09:18:00`; `120` | Map collection gaps and apply the WS-17 clock offset only to records that require it. |
| T13 | `6364`; `browser.exe`; `WS-17`; `23:22:00` | Inspect the prepared native process record and distinguish its acquisition timestamp from the historical timeline. |
| T14 | `BriefSync`; `brief-viewer.exe`; `23:22:01`; `no` | Inspect the prepared task record; its lab acquisition time must not receive the historical offset. |
| T15 | `6364`; `7644`; `browser.exe`; `C:/Temp/move-cache.txt` | Read the prepared memory process tree and command-line cache argument. |
| T16 | `6364`; `198.51.100.77`; `443`; `no` | Correlate the prepared connection snapshot, while keeping the limitation that a connection does not prove a human read the payload. |
| T17 | `198.51.100.77`; `/upload`; `BriefSync`; `no` | Inspect the harmless training binary statically in Cutter; embedded strings are configuration evidence, not proof of execution. |
| T18 | `3`; `cached v3`; `other version`; `no` | Follow the `classify_version` function: input 3 returns `cached v3`, other inputs return `other version`, and a branch alone does not prove incident execution. |
| T19 | `req-72`; `3`; `09:06:00`; `no` | Match the DLP body metadata to the upload request and catalog hash; an HTTP acknowledgement does not prove human reading. |
| T20 | `3`; `no`; `no`; `no` | Synthesize the evidence: v3 transmission is supported, roster disclosure is denied, WS-31 remains unresolved, and intent is not established. |

## Dependency releases observed

The run demonstrated the follow-up release chain rather than treating all
tickets as immediately available:

- T07 appeared after T06 and released `identity/late-auth.csv`.
- T09 appeared after T08 and released `server/version-comparison.csv`.
- T11 appeared after T10 and released `hunting/late-inventory.csv`.
- T19 appeared after T01 and T05 and released the DLP body and metadata.
- T20 appeared after T07, T09, T11, and T19.

The operator did not manually copy evidence, award points, create tickets, or
edit receipts. The controller outbox handled the releases and the final
diagnostics reported no pending deliveries or failures. The operator procedure
is documented in [facilitator-evidence-release.md](../../../facilitator-evidence-release.md).

## Screenshots and walkthrough evidence

The rehearsal used screenshot capture after each answer interaction in the
isolated browser, including all four final T18 submissions and the completed
state. The repository retains the earlier rehearsal's screenshot archive and
walkthrough/defect notes under this directory; the current run's authoritative
completion is the server state and UI receipt recorded above.

## Defects and operational findings

1. The participant answer nonce was empty on a fresh session and caused 403
   answer submissions. This was fixed in `b6252ad` by initializing the nonce
   before POST validation.
2. A shared browser session cannot safely represent ten simultaneous team
   identities. The rehearsal therefore serialized identities. Production should
   provide one isolated browser profile/session per team.
3. IRIS still renders raw private-bind-IP links in some queue pages even when
   the public certificate hostname is valid. The CTFd links were corrected;
   the remaining IRIS URL derivation is a source-level follow-up.
4. `ridge.deploy start` still applies a certificate guard against the private
   bind address when the public Tailscale certificate is used. This rerun was
   started in the controller's running mode after that guard; the deployment
   command should be fixed and retested before production.
5. One delegated browser agent hit an agent-side browser availability error.
   Direct isolated-browser takeover completed the role without changing the
   event logic.

The earlier blocked attempt remains documented in `README.md`; it is not the
result of this completed rerun.
