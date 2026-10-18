# Operation Silent Ridge — Team 7 rehearsal record

## Execution status

This is a blocked-run record for `ridge-oct26-fresh`, prepared on 2026-10-18.
The requested participant hostname was tested only from an isolated browser
session. The isolated browser could load a public HTTPS control page, but its
navigation to the supplied rehearsal hostname timed out before any participant
surface rendered. The user's logged-in Chrome was not used.

The host-side read-only connectivity check showed that the hostname resolves on
the local Tailscale interface and that the CTFd port is reachable, but that
does not make the hostname available to the isolated browser runtime. No
browser bypass, HTTP fallback, certificate bypass, or alternate logged-in
browser was used.

## Exact counts

| Item | Result |
|---|---:|
| Assigned tickets | 2 (T07, T17) |
| Questions in scope | 8 |
| Tickets claimed | 0 |
| Answers submitted | 0 / 8 |
| Visible `Correct` receipts | 0 / 8 |
| Successful-answer screenshots | 0 / 8 |
| Queue/claim screenshots | 0 |
| Error-state screenshots | 0 |
| Recorded blocking defects | 1 |

## Intended workflow and evidence contract

The repository acceptance matrix and `docs/walkthrough/CTF-WALKTHROUGH.md`
specify the following sequence: open IRIS, claim exactly one ticket, read the
question card in CTFd, inspect the named evidence through the named tool in the
team desktop, enter only the requested value, and verify the visible `Correct`
receipt after submission. Times use `HH:MM:SS` UTC; case and outer whitespace
are ignored. Findings must stay bounded by the supplied evidence and retain the
matrix limitation.

Because the rehearsal surface never rendered, none of the routes below were
executed and none of the expected values were submitted. These are the
repository-derived plans retained for the next attempt.

## T07 — Test the effect of the password reset

Evidence route: Wazuh Discover, `/evidence/wazuh/telemetry.jsonl`, filter
`data.action:session_refresh`. The timed view requires an absolute scenario-date
UTC range; the default relative range can show no results even when the replay
is present.

### T07-Q1

- Expected value: `09:20:00`
- Explanation: The first `session_refresh` record is the documented 09:20
  event; the answer contract asks for the time only, not a full timestamp.
- Limitation: Historical replay is not a live observation; missing telemetry is
  not proof that an event did not occur.
- Screenshot: not captured; the page was unreachable in the isolated browser.

### T07-Q2

- Expected value: `09:26:00`
- Explanation: The later `session_refresh` record is at 09:26, showing that
  session activity continued after the reset event.
- Limitation: Historical replay is not a live observation; missing telemetry is
  not proof that an event did not occur.
- Screenshot: not captured; the page was unreachable in the isolated browser.

### T07-Q3

- Expected value: `S-41`
- Explanation: The refresh records are tied to session `S-41`; the session
  identifier is the supported correlation value rather than an IP-based identity
  claim.
- Limitation: Historical replay is not a live observation; missing telemetry is
  not proof that an event did not occur.
- Screenshot: not captured; the page was unreachable in the isolated browser.

### T07-Q4

- Expected value: `session revocation`
- Explanation: The reset is insufficient to contain an already active session;
  the bounded control conclusion is that explicit session revocation is needed.
- Limitation: Historical replay is not a live observation; missing telemetry is
  not proof that an event did not occur.
- Screenshot: not captured; the page was unreachable in the isolated browser.

## T17 — Inspect the harmless training binary configuration

Evidence route: Guacamole team desktop, Cutter, static inspection of
`/evidence/binary/brief-viewer-training`, `Windows > Strings`. The binary is a
harmless training surrogate and must not be executed.

### T17-Q1

- Expected value: `198.51.100.77`
- Explanation: The Windows strings view contains the configured destination
  address; static strings support that configuration observation.
- Limitation: This harmless training surrogate demonstrates static inspection,
  not behavior of an acquired incident executable.
- Screenshot: not captured; the Guacamole desktop was unreachable in the
  isolated browser.

### T17-Q2

- Expected value: `/upload`
- Explanation: The Windows strings view contains the upload path; the answer
  is the literal path requested by the question.
- Limitation: This harmless training surrogate demonstrates static inspection,
  not behavior of an acquired incident executable.
- Screenshot: not captured; the Guacamole desktop was unreachable in the
  isolated browser.

### T17-Q3

- Expected value: `BriefSync`
- Explanation: The binary's strings include the configured product/service name
  `BriefSync`.
- Limitation: This harmless training surrogate demonstrates static inspection,
  not behavior of an acquired incident executable.
- Screenshot: not captured; the Guacamole desktop was unreachable in the
  isolated browser.

### T17-Q4

- Expected value: `no`
- Explanation: The static strings route does not establish execution; the
  bounded answer is `no`, consistent with the instruction to inspect statically
  and never execute the binary.
- Limitation: This harmless training surrogate demonstrates static inspection,
  not behavior of an acquired incident executable.
- Screenshot: not captured; the Guacamole desktop was unreachable in the
  isolated browser.

## Defect and retry note

Retry from an environment whose isolated browser can resolve and route the
participant hostname over Tailscale. On retry, capture the IRIS queue before
claim, the claimed T07/T17 states, each post-submit page with the visible
`Correct` receipt, and any naturally occurring error page. Do not infer a
successful claim or answer from a network check alone.
