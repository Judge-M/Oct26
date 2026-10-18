# Operation Silent Ridge — Team 10 rehearsal walkthrough

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Role: Team 10; requested scope `T10` and `T20`  
Hostname: `https://desktop-t5pf26o.tail799fee.ts.net`  
Browser: isolated ChatGPT in-app browser session; no logged-in Chrome was used

## Result summary

| Measure | Result |
|---|---:|
| Tickets successfully claimed | 1/2 (`T10` yes; `T20` unavailable) |
| Questions reached | 0/8 |
| Answers submitted | 0/8 |
| Visible `Correct` results | 0/8 |
| Incorrect submissions | 0 |
| Successful evidence inspections | 0 live Wazuh records; route was blocked |
| Screenshots captured | 12 |

T10 was claimed successfully and was still held by `team-10` at final verification. T20 did not appear in the live IRIS queue, so there was no claim control to use and no attempt was made to claim another ticket. The queue's available list remained `T05, T08, T12, T13, T14, T15, T16, T17, T18`.

CTFd rendered `500 — An Internal Server Error has occurred` for `/silent-ridge` and `/challenges`, including after signing in as Team 10. No question card or answer form was visible, so no answer could be submitted or verified as `Correct`.

Wazuh opened an existing session as `team1` with permission errors for telemetry search. After logout, the supplied Team 10 login was rejected as invalid. The Guacamole Wazuh desktop shortcut selected successfully but produced no visible application window.

## Source contract used

The repository acceptance matrix and current walkthrough define these exact answer contracts. They are recorded here as expected values only; none were accepted live.

### T10 — Test a benign comparator

Route: IRIS claim T10 → Wazuh Discover → index `silent-ridge-timed` → set the absolute scenario range covering 2026-10-15 08:00–10:30 UTC → filter `data.host:WS-22` → inspect the selected telemetry record.

| Question | Expected value | Evidence path | Limitation |
|---|---|---|---|
| T10-Q1 | `WS-22` | `/evidence/wazuh/telemetry.jsonl` | Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur. |
| T10-Q2 | `Exercise IT` | `/evidence/wazuh/telemetry.jsonl` | Same historical-replay limitation. |
| T10-Q3 | `C:/Program Files/Approved/briefsync.exe` | `/evidence/wazuh/telemetry.jsonl` | Same historical-replay limitation. |
| T10-Q4 | `r.chen` | `/evidence/wazuh/telemetry.jsonl` | Same historical-replay limitation. |

Live result: not submitted; CTFd question route returned HTTP 500 and Wazuh access was unavailable.

### T20 — Test the limits of the overall exposure conclusion

Route: T20 is a gated Wazuh ticket. The walkthrough states that it requires T07, T09, T11, and T19 to be complete. In the live Team 10 queue, T20 was absent and no claim control was rendered.

| Question | Expected value | Evidence path | Selection / limitation |
|---|---|---|---|
| T20-Q1 | `3` | `/evidence/wazuh/telemetry.jsonl` | Filter `data.request:req-72`; historical replay is not a live observation. |
| T20-Q2 | `no` | `/evidence/wazuh/telemetry.jsonl` | Same selected request record; no positive receipt flag is established. |
| T20-Q3 | `no` | `/evidence/wazuh/telemetry.jsonl` | Same selected request record; no additional transfer flag is established. |
| T20-Q4 | `no` | `/evidence/wazuh/telemetry.jsonl` | Same selected request record; the record does not establish human intent. |

Live result: not claimable; no T20 question form was reached.

## Live navigation and evidence

1. Opened the public hostname in the isolated in-app browser. No raw IP and no logged-in Chrome session were used.
2. Re-authenticated IRIS as Team 10 and opened `/silent-ridge`. The queue showed `Team: team-10`, `Exercise: running`, and T10 available.
3. Captured the pre-claim queue, claimed T10, and verified the visible state `You hold: T10`.
4. Opened CTFd `/silent-ridge`. The page rendered `500 — An Internal Server Error has occurred`; `/challenges` rendered the same error.
5. Signed out of the stale CTFd session and signed in as Team 10. The post-login destination still rendered HTTP 500. No challenge card or answer input was visible.
6. Opened Guacamole, signed out of the stale Team 9 desktop session, and signed in as Team 10. The Guacamole menu visibly identified `desktop-10` and `team10`.
7. Selected and launched the desktop Wazuh shortcut. The desktop remained unchanged, so this was recorded as a no-op launcher defect.
8. Opened Wazuh directly. The existing session identified `team1` and displayed a telemetry permission error. After logout, the Team 10 credentials were rejected with `Invalid username or password. Please try again.`
9. Re-authenticated IRIS as Team 10 after the cross-surface session changes. Final queue verification showed T10 still held by Team 10 and T20 still absent.

No evidence file was modified, no binary was executed, no other ticket was claimed, and no password or secret is recorded in this walkthrough.

## Screenshot manifest

All files are under `screenshots/` beside this walkthrough.

| File | Purpose |
|---|---|
| `iris-team10-queue-before-claim.png` | Team 10 queue before claiming; T10 available. |
| `iris-team10-t10-claimed-queue.png` | Successful T10 claim and queue state. |
| `iris-team10-t10-final-queue.png` | Final Team 10 verification; T10 held and T20 absent. |
| `ctfd-team10-silent-ridge-500.png` | CTFd `/silent-ridge` HTTP 500. |
| `ctfd-team10-post-login-500.png` | CTFd HTTP 500 after Team 10 login. |
| `ctfd-logout-404.png` | CTFd logout link returned 404. |
| `guacamole-team10-desktop-menu.png` | Guacamole menu identifying `desktop-10` / Team 10. |
| `guacamole-wazuh-launcher-noop.png` | Wazuh shortcut selected/activated with no visible application launch. |
| `wazuh-team1-permission-error.png` | Existing Wazuh session showed `team1` and telemetry permission failure. |
| `wazuh-team10-login-error.png` | Wazuh rejected the Team 10 login. |
| `iris-queue-forbidden-after-claim.png` | IRIS 403 observed after switching sessions across shared-host surfaces. |
| `iris-team10-t20-unavailable.png` | Additional IRIS verification attempt that returned the same 403 state; final queue evidence is in `iris-team10-t10-final-queue.png`. |

## Credentials handling

No password, token, API key, or other secret is included in this walkthrough or the defect notes.
