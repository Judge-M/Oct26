# Operation Silent Ridge — Rehearsal Defects

- Event: `ridge-oct26-fresh`
- Date: 2026-10-18
- Browser context: isolated ChatGPT in-app browser; no logged-in Chrome session used.

## DEF-001 — Public rehearsal hostname unreachable from the isolated browser

- Severity: Blocker
- Status: Open / requires environment or service-owner follow-up
- Host: `https://desktop-t5pf26o.tail799fee.ts.net`
- Observed: navigation did not reach an application response. The browser displayed `This site can't be reached` and `ERR_CONNECTION_TIMED_OUT`; the page stated that the hostname took too long to respond.
- Independent read-only check: DNS resolution returned no record in the current environment; TCP/443 test returned `TcpTestSucceeded: false`.
- Impact: CTFd, IRIS, Guacamole, and Wazuh checks could not proceed to login or application pages. This prevents verification of dashboards, teams/users, challenge/question availability, event state, connections/mappings, Wazuh search, and application-level auth/index errors.
- Evidence: `00-host-connection-error.png`, `ctfd-host-error.png`, `iris-host-error.png`, `guacamole-host-error.png`, `wazuh-host-error.png`
- Reproduction: in a fresh isolated browser session, navigate to the target hostname over HTTPS.
- Safety: no configuration, credentials, passwords, tickets, or data were modified.

## Surface result summary

| Surface | Result | Reason | Evidence |
|---|---|---|---|
| CTFd admin | Failed / not reached | Common hostname timeout before login page | `ctfd-host-error.png` |
| IRIS administrator | Failed / not reached | Common hostname timeout before application page | `iris-host-error.png` |
| Guacamole facilitator | Failed / not reached | Common hostname timeout before login page | `guacamole-host-error.png` |
| Wazuh dashboard | Failed / not reached | Common hostname timeout before login page | `wazuh-host-error.png` |

