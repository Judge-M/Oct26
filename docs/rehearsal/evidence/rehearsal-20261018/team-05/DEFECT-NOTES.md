# Team 5 rehearsal defect notes

## D-01 — IRIS role/case mismatch blocks the queue

- The supplied IRIS role name with the hyphen was rejected by the live login form.
- The supplied unhyphenated Team 5 account was accepted, but the only visible case was `#1 - Initial Demo` and the dashboard banner said `Access denied to #1`.
- The attributed-task table was empty, so no incident queue or claim control was available for T05/T15.
- Receipt: `iris-team5-access-denied.png`.

## D-02 — CTFd fixed-host navigation timeout

- Repeated attempts to open the CTFd login URL in the isolated in-app browser timed out during page navigation and left blank tabs.
- Impact: no CTFd question forms, submissions, or visible `Correct` receipts could be verified.

## D-03 — Cross-tab/session contamination in isolated browser

- Fresh IRIS/Guacamole tabs initially displayed other team identities (including team1/team2/team3/team6) before explicit logout/login.
- Receipt: `iris-authentication-required.png` captures an authentication-required state after this stale-session behavior.
- Impact: the browser session cannot be assumed to represent Team 5 without an explicit logout and re-login on each surface.

## D-04 — Team 5 desktop shortcuts did not launch tools

- Guacamole login succeeded and produced `desktop-05`; the expected tool and workflow shortcuts were visible.
- Double-click/keyboard launch attempts for Autopsy and Questions and help did not open an application window.
- Receipt: `guacamole-team05-desktop.png`.

## Completion status

- T05: 0/4 submitted; 0/4 live-correct verified.
- T15: 0/4 submitted; 0/4 live-correct verified.
- Admin surface checks: not started.
- Repository changes: none; no commit or push performed.
