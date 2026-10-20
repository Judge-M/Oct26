# Team 01 full browser rehearsal — 2026-10-19

This is a live one-team acceptance run against the event machine at revision `3f78b8c` plus test-only follow-up `73a12bd`. The participant used the isolated browser, registered through the public landing page, logged into IRIS and CTFd, claimed every ticket in the order it became available, opened the explicit walkthrough for every question, and submitted all 80 answers through the UI.

Final observed state: **20/20 ticket stages complete and 80 points**. The screenshots contain no generated passwords or private registration links.

## Participant path

1. Open the registration page and reserve a team.
2. Bookmark the private handout URL and wait for provisioning.
3. Sign into CTFd with a generated participant seat and IRIS with the team account.
4. Claim the next available ticket in IRIS.
5. Return to the CTFd Questions page, open Help level 3 when needed, and submit each answer.
6. Repeat until the queue reports completion, then verify the scoreboard.

Key evidence: [registration](screenshots/02-registration-fixed.png), [pending provisioning](screenshots/03-team-registration-pending.png), [CTFd brief](screenshots/06-ctfd-initial-brief.png), [IRIS queue](screenshots/10-iris-queue-before-t01.png), [T01 claimed](screenshots/11-iris-t01-claimed.png), [all questions complete](screenshots/17-all-80-complete.png), and [final scoreboard](screenshots/18-scoreboard-final.png).

## Release behavior observed

The per-team queue released later work automatically: T07 and T19 appeared after six completed tickets, T09 appeared after T08, T11 appeared at the 10/20 midpoint, and T20 appeared only after 19/20 stages. This confirms team-local staged release without an administrator clicking a release control during this run.

## Question-by-question walkthrough

### T01

#### T01-Q1 — Which workstation requested plan-v3?

- Answer: `WS-17`
- Explanation: WS-17 is the workstation associated with the plan-v3 request.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T01-Q1 explicit walkthrough](screenshots/12-T01-Q1-walkthrough.png)

#### T01-Q2 — What request identifier links the plan download?

- Answer: `req-71`
- Explanation: The plan download is correlated by request identifier req-71.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T01-Q2 explicit walkthrough](screenshots/13-T01-Q2-walkthrough.png)

#### T01-Q3 — What request identifier records the upload?

- Answer: `req-72`
- Explanation: Request req-72 identifies the outbound upload.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T01-Q3 explicit walkthrough](screenshots/14-T01-Q3-walkthrough.png)

#### T01-Q4 — Which external address appears in the upload record?

- Answer: `198.51.100.77`
- Explanation: The upload record identifies 198.51.100.77 as its external destination.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T01-Q4 explicit walkthrough](screenshots/15-T01-Q4-walkthrough.png)

### T02

#### T02-Q1 — Which name resolved to the external destination?

- Answer: `relay.archive.example`
- Explanation: The DNS record maps relay.archive.example to an address.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T02-Q1 explicit walkthrough](screenshots/17-T02-Q1-walkthrough.png)

#### T02-Q2 — What address did it resolve to?

- Answer: `198.51.100.77`
- Explanation: The DNS answer is 198.51.100.77.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T02-Q2 explicit walkthrough](screenshots/18-T02-Q2-walkthrough.png)

#### T02-Q3 — Which client made that lookup?

- Answer: `10.26.10.17`
- Explanation: The recorded DNS client is WS-17 at 10.26.10.17.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T02-Q3 explicit walkthrough](screenshots/19-T02-Q3-walkthrough.png)

#### T02-Q4 — What TTL was returned, in seconds?

- Answer: `60`
- Explanation: The DNS response records a 60-second TTL.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.
- Screenshot: [T02-Q4 explicit walkthrough](screenshots/20-T02-Q4-walkthrough.png)

### T03

#### T03-Q1 — At what normalized UTC time was the viewer downloaded?

- Answer: `08:57:00`
- Explanation: The browser export records the viewer download at 08:57:00 UTC.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T03-Q1 explicit walkthrough](screenshots/22-T03-Q1-walkthrough.png)

#### T03-Q2 — What was the downloaded filename?

- Answer: `brief-viewer.exe`
- Explanation: The recorded download filename is brief-viewer.exe.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T03-Q2 explicit walkthrough](screenshots/23-T03-Q2-walkthrough.png)

#### T03-Q3 — What host served the download URL?

- Answer: `briefs.helpdesk.example`
- Explanation: The download URL names briefs.helpdesk.example; this does not establish the original delivery mechanism.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T03-Q3 explicit walkthrough](screenshots/24-T03-Q3-walkthrough.png)

#### T03-Q4 — What was the recorded target directory?

- Answer: `C:/Downloads`
- Explanation: The browser target path places the download in C:/Downloads.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T03-Q4 explicit walkthrough](screenshots/25-T03-Q4-walkthrough.png)

### T04

#### T04-Q1 — What task name was registered?

- Answer: `BriefSync`
- Explanation: The registered task is named BriefSync.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T04-Q1 explicit walkthrough](screenshots/27-T04-Q1-walkthrough.png)

#### T04-Q2 — Which process registered the task?

- Answer: `brief-viewer.exe`
- Explanation: The task-registration record names brief-viewer.exe as the registering process.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T04-Q2 explicit walkthrough](screenshots/28-T04-Q2-walkthrough.png)

#### T04-Q3 — What trigger was recorded?

- Answer: `user logon`
- Explanation: The recorded task trigger is user logon.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T04-Q3 explicit walkthrough](screenshots/29-T04-Q3-walkthrough.png)

#### T04-Q4 — What is the corrected task registration time?

- Answer: `09:08:00`
- Explanation: After subtracting the documented 120-second device offset, task registration occurred at 09:08:00 UTC.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T04-Q4 explicit walkthrough](screenshots/30-T04-Q4-walkthrough.png)

### T05

#### T05-Q1 — What patrol name appears in the recovered cache?

- Answer: `LANTERN`
- Explanation: The recovered cache names fictional patrol LANTERN.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T05-Q1 explicit walkthrough](screenshots/32-T05-Q1-walkthrough.png)

#### T05-Q2 — What version appears in the cached brief?

- Answer: `3`
- Explanation: The recovered cache contains movement brief version 3.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T05-Q2 explicit walkthrough](screenshots/33-T05-Q2-walkthrough.png)

#### T05-Q3 — What sector is named?

- Answer: `AMBER`
- Explanation: The cached version names sector AMBER.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T05-Q3 explicit walkthrough](screenshots/34-T05-Q3-walkthrough.png)

#### T05-Q4 — What check-in word is present?

- Answer: `CEDAR`
- Explanation: The cached version includes check-in word CEDAR.
- Why it matters: Confirm which movement brief is actually supported before broader identity or intent claims are made.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T05-Q4 explicit walkthrough](screenshots/35-T05-Q4-walkthrough.png)

### T06

#### T06-Q1 — Which account was assigned S-41?

- Answer: `m.ellis`
- Explanation: The identity record assigns session S-41 to m.ellis.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T06-Q1 explicit walkthrough](screenshots/37-T06-Q1-walkthrough.png)

#### T06-Q2 — What external refresh time is recorded?

- Answer: `09:03:00`
- Explanation: The external S-41 refresh is timestamped 09:03:00 UTC.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T06-Q2 explicit walkthrough](screenshots/38-T06-Q2-walkthrough.png)

#### T06-Q3 — Which MFA field value appears on that refresh?

- Answer: `previous_claim`
- Explanation: The refresh carries previous_claim, rather than a newly challenged MFA result.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T06-Q3 explicit walkthrough](screenshots/39-T06-Q3-walkthrough.png)

#### T06-Q4 — Did the separate 09:05 password login succeed?

- Answer: `no`
- Explanation: The separate password-login attempt at 09:05 failed; it must not be conflated with session refresh success.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T06-Q4 explicit walkthrough](screenshots/40-T06-Q4-walkthrough.png)

### T07

#### T07-Q1 — When did the password reset occur?

- Answer: `09:20:00`
- Explanation: The password-reset record is timestamped 09:20:00 UTC.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T07-Q1 explicit walkthrough](screenshots/42-T07-Q1-walkthrough.png)

#### T07-Q2 — What is the late successful session refresh time?

- Answer: `09:26:00`
- Explanation: A later session refresh succeeded at 09:26:00 UTC.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T07-Q2 explicit walkthrough](screenshots/43-T07-Q2-walkthrough.png)

#### T07-Q3 — Which session persisted?

- Answer: `S-41`
- Explanation: The later successful refresh reused S-41.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T07-Q3 explicit walkthrough](screenshots/44-T07-Q3-walkthrough.png)

#### T07-Q4 — Which separate policy action invalidates issued sessions?

- Answer: `session revocation`
- Explanation: The supplied identity policy treats explicit session revocation separately from a password reset. No containment change was performed by participants.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T07-Q4 explicit walkthrough](screenshots/45-T07-Q4-walkthrough.png)

### T08

#### T08-Q1 — Which object was successfully downloaded in req-71?

- Answer: `plan-v3`
- Explanation: Request req-71 returned plan-v3.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T08-Q1 explicit walkthrough](screenshots/47-T08-Q1-walkthrough.png)

#### T08-Q2 — What status did the roster request return?

- Answer: `403`
- Explanation: The roster request returned HTTP 403.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T08-Q2 explicit walkthrough](screenshots/48-T08-Q2-walkthrough.png)

#### T08-Q3 — How many roster body bytes were returned?

- Answer: `0`
- Explanation: The denied roster request returned zero body bytes.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T08-Q3 explicit walkthrough](screenshots/49-T08-Q3-walkthrough.png)

#### T08-Q4 — Which request identifies the denied roster access?

- Answer: `req-75`
- Explanation: Request req-75 identifies the denied roster access, not a successful disclosure.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Prepared evidence is limited to the specified collection. Presence of an artifact is not proof of every related action.
- Screenshot: [T08-Q4 explicit walkthrough](screenshots/50-T08-Q4-walkthrough.png)

### T09

#### T09-Q1 — When did v4 supersede v3, UTC?

- Answer: `09:10:00`
- Explanation: The supplied version history records v4 superseding v3 at 09:10:00 UTC.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T09-Q1 explicit walkthrough](screenshots/52-T09-Q1-walkthrough.png)

#### T09-Q2 — What sector does v4 specify?

- Answer: `BLUE`
- Explanation: Version 4 specifies sector BLUE.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T09-Q2 explicit walkthrough](screenshots/53-T09-Q2-walkthrough.png)

#### T09-Q3 — What movement window does v4 specify?

- Answer: `10:30-11:30Z`
- Explanation: Version 4 specifies the 10:30â€“11:30Z movement window.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T09-Q3 explicit walkthrough](screenshots/54-T09-Q3-walkthrough.png)

#### T09-Q4 — Which check-in word remains unchanged?

- Answer: `CEDAR`
- Explanation: CEDAR is unchanged between the supplied v3 and v4 records.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T09-Q4 explicit walkthrough](screenshots/55-T09-Q4-walkthrough.png)

### T10

#### T10-Q1 — Which host has the approved similarly named task?

- Answer: `WS-22`
- Explanation: WS-22 has a similarly named approved task; its name alone is not a compromise indicator.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T10-Q1 explicit walkthrough](screenshots/57-T10-Q1-walkthrough.png)

#### T10-Q2 — Who published its application?

- Answer: `Exercise IT`
- Explanation: The WS-22 inventory identifies Exercise IT as publisher.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T10-Q2 explicit walkthrough](screenshots/58-T10-Q2-walkthrough.png)

#### T10-Q3 — What is its executable path?

- Answer: `C:/Program Files/Approved/briefsync.exe`
- Explanation: The approved WS-22 application path is C:/Program Files/Approved/briefsync.exe.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T10-Q3 explicit walkthrough](screenshots/59-T10-Q3-walkthrough.png)

#### T10-Q4 — Which planner account reads v4?

- Answer: `r.chen`
- Explanation: The server audit records r.chen as the planner reading v4.
- Why it matters: Avoid blaming an account or host from a name match when the authentication and access records say something narrower.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T10-Q4 explicit walkthrough](screenshots/60-T10-Q4-walkthrough.png)

### T11

#### T11-Q1 — What task name appears on WS-31?

- Answer: `BriefSync`
- Explanation: WS-31 inventory contains a task named BriefSync, creating an unresolved scope lead.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T11-Q1 explicit walkthrough](screenshots/62-T11-Q1-walkthrough.png)

#### T11-Q2 — At what UTC time was the inventory observed?

- Answer: `08:45:00`
- Explanation: The WS-31 inventory observation is timestamped 08:45:00 UTC.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T11-Q2 explicit walkthrough](screenshots/63-T11-Q2-walkthrough.png)

#### T11-Q3 — When did endpoint collection stop?

- Answer: `08:50:00`
- Explanation: WS-31 endpoint collection stopped at 08:50:00 UTC.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T11-Q3 explicit walkthrough](screenshots/64-T11-Q3-walkthrough.png)

#### T11-Q4 — Does task inventory alone prove execution?

- Answer: `no`
- Explanation: Task inventory alone does not establish execution on WS-31. Further collection would be required.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T11-Q4 explicit walkthrough](screenshots/65-T11-Q4-walkthrough.png)

### T12

#### T12-Q1 — Which workstation has no network collection?

- Answer: `WS-31`
- Explanation: The coverage record lists no network collection for WS-31.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T12-Q1 explicit walkthrough](screenshots/67-T12-Q1-walkthrough.png)

#### T12-Q2 — When does the DOCS-1 collection gap start?

- Answer: `09:14:00`
- Explanation: DOCS-1 audit collection has a gap beginning at 09:14:00 UTC.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T12-Q2 explicit walkthrough](screenshots/68-T12-Q2-walkthrough.png)

#### T12-Q3 — When does that gap end?

- Answer: `09:18:00`
- Explanation: DOCS-1 audit collection resumes at 09:18:00 UTC.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T12-Q3 explicit walkthrough](screenshots/69-T12-Q3-walkthrough.png)

#### T12-Q4 — How many seconds fast is the WS-17 device clock?

- Answer: `120`
- Explanation: The documented WS-17 device offset is 120 seconds fast; normalized records must not receive a second correction.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T12-Q4 explicit walkthrough](screenshots/70-T12-Q4-walkthrough.png)

### T13

#### T13-Q1 — Which process ID belongs to the acquired viewer?

- Answer: `6364`
- Explanation: Native Security record 606 records viewer PID 6364.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T13-Q1 explicit walkthrough](screenshots/72-T13-Q1-walkthrough.png)

#### T13-Q2 — What is the basename of its parent executable?

- Answer: `browser.exe`
- Explanation: The native process event names browser.exe as the parent training surrogate.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T13-Q2 explicit walkthrough](screenshots/73-T13-Q2-walkthrough.png)

#### T13-Q3 — Which scenario workstation is this lab reconstruction mapped to?

- Answer: `WS-17`
- Explanation: The acquisition manifest maps this isolated lab reconstruction to WS-17; the original computer name is preserved.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T13-Q3 explicit walkthrough](screenshots/74-T13-Q3-walkthrough.png)

#### T13-Q4 — What actual acquisition UTC time is recorded for process creation?

- Answer: `23:22:00`
- Explanation: The reconstructed process was created at 23:22:00 UTC on 2026-09-15; no historic clock correction applies.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T13-Q4 explicit walkthrough](screenshots/75-T13-Q4-walkthrough.png)

### T14

#### T14-Q1 — What task name was registered?

- Answer: `BriefSync`
- Explanation: Native Security record 607 records the BriefSync task.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T14-Q1 explicit walkthrough](screenshots/77-T14-Q1-walkthrough.png)

#### T14-Q2 — What executable does the task target?

- Answer: `brief-viewer.exe`
- Explanation: The captured task XML targets the harmless brief-viewer.exe training surrogate.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T14-Q2 explicit walkthrough](screenshots/78-T14-Q2-walkthrough.png)

#### T14-Q3 — What actual acquisition UTC time is recorded for registration?

- Answer: `23:22:01`
- Explanation: The reconstructed task was registered at 23:22:01 UTC on 2026-09-15.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T14-Q3 explicit walkthrough](screenshots/79-T14-Q3-walkthrough.png)

#### T14-Q4 — Should the historical 120-second offset be applied to this native acquisition?

- Answer: `no`
- Explanation: Acquisition timestamps describe the lab capture and must not be rewritten as historical incident timestamps.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T14-Q4 explicit walkthrough](screenshots/80-T14-Q4-walkthrough.png)

### T15

#### T15-Q1 — What viewer PID is present in the prepared capture?

- Answer: `6364`
- Explanation: Volatility recovered viewer PID 6364 at kernel virtual offset 0xc98352279080.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T15-Q1 explicit walkthrough](screenshots/82-T15-Q1-walkthrough.png)

#### T15-Q2 — What parent PID is recorded?

- Answer: `7644`
- Explanation: The recovered viewer process records parent PID 7644.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T15-Q2 explicit walkthrough](screenshots/83-T15-Q2-walkthrough.png)

#### T15-Q3 — What executable belongs to the parent?

- Answer: `browser.exe`
- Explanation: The recovered parent process name is browser.exe; it is a training surrogate.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T15-Q3 explicit walkthrough](screenshots/84-T15-Q3-walkthrough.png)

#### T15-Q4 — What path is supplied to the viewer as its cache argument?

- Answer: `C:/Temp/move-cache.txt`
- Explanation: The memory-derived command line contains cache argument C:/Temp/move-cache.txt.
- Why it matters: Collection gaps and clock corrections can change the conclusion; apply each correction once and keep unresolved systems unresolved.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T15-Q4 explicit walkthrough](screenshots/85-T15-Q4-walkthrough.png)

### T16

#### T16-Q1 — Which PID owns the recorded training connection?

- Answer: `6364`
- Explanation: The guest's native connection snapshot records PID 6364.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T16-Q1 explicit walkthrough](screenshots/87-T16-Q1-walkthrough.png)

#### T16-Q2 — What remote address is recorded?

- Answer: `198.51.100.77`
- Explanation: 198.51.100.77 was a guest-local loopback address in this reconstruction; no Internet traffic occurred.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T16-Q2 explicit walkthrough](screenshots/88-T16-Q2-walkthrough.png)

#### T16-Q3 — What remote port is recorded?

- Answer: `443`
- Explanation: The native snapshot records TCP remote port 443.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T16-Q3 explicit walkthrough](screenshots/89-T16-Q3-walkthrough.png)

#### T16-Q4 — Does this connection record prove a human read a payload?

- Answer: `no`
- Explanation: This is a live acquisition sidecar, not a validated memory connection finding or evidence of human reading.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.
- Screenshot: [T16-Q4 explicit walkthrough](screenshots/90-T16-Q4-walkthrough.png)

### T17

#### T17-Q1 — What destination is embedded as configuration?

- Answer: `198.51.100.77`
- Explanation: The training surrogate contains destination string 198.51.100.77.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T17-Q1 explicit walkthrough](screenshots/92-T17-Q1-walkthrough.png)

#### T17-Q2 — What path is embedded as configuration?

- Answer: `/upload`
- Explanation: The training surrogate contains configuration path /upload.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T17-Q2 explicit walkthrough](screenshots/93-T17-Q2-walkthrough.png)

#### T17-Q3 — What task label appears as a string?

- Answer: `BriefSync`
- Explanation: The training surrogate contains task-label string BriefSync.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T17-Q3 explicit walkthrough](screenshots/94-T17-Q3-walkthrough.png)

#### T17-Q4 — Does this training binary perform network calls?

- Answer: `no`
- Explanation: The supplied training surrogate performs no network calls; its strings are for static inspection.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T17-Q4 explicit walkthrough](screenshots/95-T17-Q4-walkthrough.png)

### T18

#### T18-Q1 — Which integer marks the cached version?

- Answer: `3`
- Explanation: The classify_version example compares its input with integer 3.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T18-Q1 explicit walkthrough](screenshots/97-T18-Q1-walkthrough.png)

#### T18-Q2 — What text is returned when the input is 3?

- Answer: `cached v3`
- Explanation: The input-3 branch returns the text cached v3.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T18-Q2 explicit walkthrough](screenshots/98-T18-Q2-walkthrough.png)

#### T18-Q3 — What text is returned for other inputs?

- Answer: `other version`
- Explanation: The other branch returns the text other version.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T18-Q3 explicit walkthrough](screenshots/99-T18-Q3-walkthrough.png)

#### T18-Q4 — Does a code branch prove the incident executed it?

- Answer: `no`
- Explanation: The existence of a static branch does not establish that it executed during the incident.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: This harmless training surrogate demonstrates static inspection, not behavior of an acquired incident executable.
- Screenshot: [T18-Q4 explicit walkthrough](screenshots/100-T18-Q4-walkthrough.png)

### T19

#### T19-Q1 — Which request is tied to the DLP body?

- Answer: `req-72`
- Explanation: The DLP metadata links the supplied body to req-72.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T19-Q1 explicit walkthrough](screenshots/102-T19-Q1-walkthrough.png)

#### T19-Q2 — What brief version matches that body?

- Answer: `3`
- Explanation: The body hash comparison matches movement brief v3.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T19-Q2 explicit walkthrough](screenshots/103-T19-Q2-walkthrough.png)

#### T19-Q3 — What upload time is recorded, UTC?

- Answer: `09:06:00`
- Explanation: The DLP upload timestamp is 09:06:00 UTC.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T19-Q3 explicit walkthrough](screenshots/104-T19-Q3-walkthrough.png)

#### T19-Q4 — Does the HTTP acknowledgment prove human reading?

- Answer: `no`
- Explanation: An HTTP acknowledgment does not prove a human read the transmitted body.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: The supplied document or export supports only the stated comparison, not human receipt or adversary intent.
- Screenshot: [T19-Q4 explicit walkthrough](screenshots/105-T19-Q4-walkthrough.png)

### T20

#### T20-Q1 — Which brief version is supported by the payload match?

- Answer: `3`
- Explanation: The matched payload supports transmission of movement brief v3.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T20-Q1 explicit walkthrough](screenshots/107-T20-Q1-walkthrough.png)

#### T20-Q2 — Is successful roster disclosure established by the denied request?

- Answer: `no`
- Explanation: The denied roster request does not establish successful roster disclosure.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T20-Q2 explicit walkthrough](screenshots/108-T20-Q2-walkthrough.png)

#### T20-Q3 — Can WS-31 be cleared with the available telemetry?

- Answer: `no`
- Explanation: The available inventory and collection gaps cannot clear WS-31.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T20-Q3 explicit walkthrough](screenshots/109-T20-Q3-walkthrough.png)

#### T20-Q4 — Does the evidence establish adversary intent?

- Answer: `no`
- Explanation: The supplied evidence does not establish adversary intent.
- Why it matters: A network connection or acknowledgment supports transmission, not human receipt, intent, or complete compromise scope.
- Evidence limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.
- Screenshot: [T20-Q4 explicit walkthrough](screenshots/110-T20-Q4-walkthrough.png)

## Defects and event-day risks found

1. **Registration POST returned 403.** The plugin used a second `registration_nonce`, while CTFd's global CSRF hook requires `session['nonce']`. Fixed and covered by the actual CTFd image smoke test.
2. **The registration worker was not alive.** A stale PID file was treated as live because `tasklist` returns exit code zero even when no process matches. Provisioning required one manual `--once` run during this rehearsal. The process check and detached launch behavior are fixed and covered by unit tests. Live deployment verification replaced the stale PID, launched the worker in a detached service session, and confirmed it remained alive.
3. **Stale configuration generated legacy IP-and-port URLs.** IRIS initially rendered `192.168.1.200:8181/8183`, and the completed team's stored workstation handout used `:8182`. The running containers and both authoritative provisioning-profile copies were corrected to the trusted hostnames on port 443. A browser recheck found no legacy links in IRIS; future registrations will use `iris.cyberexperts.org`, `ctfd.cyberexperts.org`, and `guac.cyberexperts.org`. The already-stored team-01 handout is historical data and was not rewritten.
4. **The CTFd-to-IRIS link reached a 401 before the first IRIS login.** Fixed: an unauthenticated request to `/silent-ridge` now redirects to `/login?next=%2Fsilent-ridge`, while an authenticated participant returns directly to the activity page.
5. **Hints were free.** Fixed: each new answer is worth 4 points, help levels 1 and 2 remain free, and explicitly unlocking the final walkthrough reduces that question to 1 point (an exact 75% cost). Existing rehearsal answers retain their historical 1-point values.
6. **The exercise elapsed clock used the global run start.** Fixed: the displayed activity clock now starts from the individual team's registration time. The live completed team showed roughly 1,600 seconds while the global run was over 39,000 seconds old.
7. **Completion initially showed three synchronization updates pending.** The participant answer state and score were already correct. A final browser check confirmed the outbox drained to **0 updates awaiting synchronization**.

## Validation receipt

- Registration page: HTTPS with the public wildcard certificate.
- Team provisioning: one team, five CTFd seats, one IRIS account, and three desktop assignments.
- Ticket lifecycle: every ticket claimed and automatically released after its fourth answer.
- Staged evidence: later tickets appeared automatically at the observed per-team milestones.
- CTFd: 80 accepted browser submissions; scoreboard showed 80 points.
- Integration: final participant page showed 0 updates awaiting synchronization.
- Assisted scoring: the live participant page advertises the 4-to-1 point policy; focused tests and the actual CTFd image smoke test verified the paid walkthrough path.
- Team-local clock: the live participant page reports elapsed time from team registration rather than the global run start.
- IRIS authentication: an unauthenticated direct activity request returns a login redirect instead of a bare 401.
- Public routing: a post-restart IRIS browser check found hostname-only links and no `192.168.x.x` or `:818x` targets.
- Registration worker: stale-PID recovery started a detached worker that remained alive during the live follow-up check.
- Evidence set: 113 sanitized PNGs in `screenshots/`.
