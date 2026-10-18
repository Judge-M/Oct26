# Operation Silent Ridge — Team 6 rehearsal walkthrough

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Role: Team 6, assigned tickets T06 and T16  
Surfaces: `https://desktop-t5pf26o.tail799fee.ts.net` with ports 8081, 8082, 8083, and 8443  
Result: 0/8 CTFd answers submitted; no `Correct` result was available because the CTFd question route returned HTTP 500.

No credentials or secret values are recorded in this walkthrough.

## Sources used

- `docs/acceptance/question-matrix.md` for the exact evidence paths, selections, expected values, and limitations.
- `docs/walkthrough/CTF-WALKTHROUGH.md` for the participant navigation and handoff sequence.
- The current Team 6 IRIS queue and the assigned desktop were inspected through the browser UI.

## Participant navigation and claim state

1. Opened the isolated in-app browser at the public hostname. No logged-in Chrome session was used.
2. Signed in to IRIS and opened `https://desktop-t5pf26o.tail799fee.ts.net:8081/silent-ridge`.
3. After re-authentication, IRIS displayed `Team: team-06`, `Exercise: running`, and `You hold: T06`. The queue showed T16 as available but did not permit a second claim while T06 was held.
4. T06 was claimed through the visible IRIS `Claim ticket` control. Screenshot: [iris-t06-claimed.png](screenshots/iris-t06-claimed.png).
5. A T16 claim attempt returned the visible error: “Ticket unavailable, another team claimed it, or exercise paused. Reload the queue.” Screenshot: [iris-t16-claim-error.png](screenshots/iris-t16-claim-error.png).
6. A later direct queue load briefly displayed `Team: team-04` while T06 remained owned by `team-06`; this was captured as a service/session defect. Screenshot: [iris-identity-switched-to-team04.png](screenshots/iris-identity-switched-to-team04.png).
7. Re-authentication restored the correct Team 6 identity and T06 ownership. Screenshot: [iris-team06-queue-after-relogin.png](screenshots/iris-team06-queue-after-relogin.png).

Queue evidence:

- [iris-team06-queue-before-claim.png](screenshots/iris-team06-queue-before-claim.png) — Team 6 queue before claiming T06.
- [iris-t06-claimed.png](screenshots/iris-t06-claimed.png) — T06 owned by Team 6.
- [iris-t16-claim-error.png](screenshots/iris-t16-claim-error.png) — T16 claim error.
- [iris-team06-queue-after-relogin.png](screenshots/iris-team06-queue-after-relogin.png) — corrected Team 6 session with T06 still held.

## CTFd result

The isolated CTFd session authenticated as the Team 6 participant and rendered the normal navigation, but opening the assigned question route `/silent-ridge` rendered `500 — An Internal Server Error has occurred`. The same result persisted in a second CTFd tab after re-authentication.

- [ctfd-internal-error-team6.png](screenshots/ctfd-internal-error-team6.png)
- [ctfd-500-after-relogin.png](screenshots/ctfd-500-after-relogin.png)

Because the question form never rendered, no answer was submitted and no `Correct` confirmation could be captured. The expected values below are recorded from the acceptance matrix for the blocked run; they are not claimed as accepted by CTFd.

## T06 — Separate password and session authentication

Evidence route: Wazuh `/evidence/wazuh/telemetry.jsonl`  
Selection: `data.session:S-41`  
Limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.

### T06-Q1

- Expected answer: `m.ellis`
- Navigation: Wazuh Discover → the event index/evidence view → filter `data.session:S-41` → inspect the session identity field.
- Justification: The selected session record identifies the surviving session actor as `m.ellis`; the answer must not be inferred from a display name elsewhere.
- Result: Not submitted; CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

### T06-Q2

- Expected answer: `09:03:00`
- Navigation: Keep the `data.session:S-41` filter and inspect the event timestamp for the session record.
- Justification: The matrix identifies `09:03:00` as the relevant time in the historical telemetry replay.
- Result: Not submitted; CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

### T06-Q3

- Expected answer: `previous_claim`
- Navigation: In the same filtered session record, inspect the field describing the superseded or prior claim.
- Justification: The record labels the superseding context `previous_claim`; this is the evidence-backed label, not a broader conclusion about intent.
- Result: Not submitted; CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

### T06-Q4

- Expected answer: `no`
- Navigation: In the same filtered telemetry, compare the session evidence with the password-authentication evidence and answer the yes/no question.
- Justification: The session record does not establish a successful password authentication for the tested claim. The historical-replay limitation still applies.
- Result: Not submitted; CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

Wazuh navigation was blocked separately: the Team 6 participant login was rejected at the Wazuh login page, and the shared reader account is a private runtime handoff not included in the public role credentials. Screenshot: [wazuh-team6-login-error.png](screenshots/wazuh-team6-login-error.png).

## T16 — Correlate the acquired connection snapshot

Evidence route: Autopsy `/evidence/prepared/windows-connections.json`  
Limitation: This is an isolated native training reconstruction with actual acquisition UTC. It does not replace the historical incident timeline. Consult the record provenance and original hash.

### T16-Q1

- Expected answer: `6364`
- Navigation: Guacamole desktop → File Manager → `/evidence/prepared/windows-connections.json` → Autopsy connection record → inspect the local/owning process field.
- Justification: The acceptance matrix identifies process ID 6364 for the selected acquired connection row.
- Result: Not submitted; T16 could not be claimed and CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

### T16-Q2

- Expected answer: `198.51.100.77`
- Navigation: In the same acquired connection row, inspect the remote address field.
- Justification: The row records the remote endpoint as `198.51.100.77`; this supports the observed connection but does not prove human receipt or intent.
- Result: Not submitted; T16 could not be claimed and CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

### T16-Q3

- Expected answer: `443`
- Navigation: In the same row, inspect the remote port field.
- Justification: The connection uses remote port 443, consistent with the prepared record; the answer is limited to the acquired snapshot.
- Result: Not submitted; T16 could not be claimed and CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

### T16-Q4

- Expected answer: `no`
- Navigation: Compare the acquired connection snapshot with the evidence limitation and answer whether the snapshot alone proves the broader exposure claim.
- Justification: A network connection supports transmission, not human receipt, intent, or complete compromise scope.
- Result: Not submitted; T16 could not be claimed and CTFd `/silent-ridge` returned HTTP 500. No Correct screenshot.

Desktop evidence captured:

- [guacamole-team6-desktop.png](screenshots/guacamole-team6-desktop.png) — Team 6 desktop session.
- The file manager visibly exposed `/evidence/prepared/` and the prepared JSON files.
- Opening `windows-connections.json` produced a “Set Default Application” dialog with no recommended viewer; the Autopsy launcher did not open. This prevented the required human Autopsy inspection.
- The desktop Web Browser launcher returned an input/output error, and the Wazuh launcher produced no visible application window. Screenshot of the no-op launcher state: [guacamole-wazuh-launcher-noop.png](screenshots/guacamole-wazuh-launcher-noop.png).

## Admin/facilitator checks

The requested facilitator/admin checks were not performed in this participant-only continuation because no facilitator/admin credential or separate admin surface was supplied. Team credentials were not used as an admin substitute. The participant surfaces were left without password changes, deletion, or event-configuration changes.

## Completion summary

- T06: claimed by Team 6; 0/4 answers submitted because CTFd returned HTTP 500 and Wazuh reader access was unavailable.
- T16: remained unclaimed after the visible IRIS claim error; 0/4 answers submitted because CTFd returned HTTP 500 and the Autopsy route was unavailable.
- Total: 0/8 accepted answers; no Correct confirmations.
