# Operation Silent Ridge — Fresh Rehearsal Admin Walkthrough

- Event: `ridge-oct26-fresh`
- Target hostname: `https://desktop-t5pf26o.tail799fee.ts.net`
- Date: 2026-10-18
- Session: isolated ChatGPT in-app browser tab; the user's logged-in Chrome was not used.
- Scope: read-only admin/operator checks only. No data deletion, event/configuration changes, ticket claims, password changes, or credential changes were performed.

## Preflight result

The target hostname did not render an application page. The isolated browser displayed **This site can't be reached** with `ERR_CONNECTION_TIMED_OUT` and stated that the hostname took too long to respond. A separate read-only local connectivity check also returned no DNS record and `TcpTestSucceeded: false` for TCP/443.

Because the shared public hostname was unreachable, login and downstream admin/operator checks could not be performed or verified. The results below are therefore **blocked/not reached**, not authentication failures.

## Surface checks

### CTFd admin

- Requested checks: admin login, dashboard, users/teams, challenge/question availability, event mode/status, and visible errors.
- Result: **FAIL — not reached**. No CTFd login page or admin surface rendered, so none of the requested CTFd checks could be verified.
- Screenshot: `ctfd-host-error.png`

### IRIS administrator

- Requested checks: administrator login if available, without changing passwords.
- Result: **FAIL — not reached**. No IRIS page or login surface rendered; availability and administrator access could not be determined.
- Screenshot: `iris-host-error.png`

### Guacamole facilitator

- Requested checks: facilitator login, connection list, and team desktop mappings without editing.
- Result: **FAIL — not reached**. No Guacamole login or connection list rendered, so team desktop mappings could not be confirmed.
- Screenshot: `guacamole-host-error.png`

### Wazuh dashboard

- Requested checks: admin login, dashboard/search, and visible authentication/index errors.
- Result: **FAIL — not reached**. No Wazuh login or dashboard/search surface rendered; no Wazuh authentication or index error could be assessed.
- Screenshot: `wazuh-host-error.png`

## Evidence

- `00-host-connection-error.png` — original isolated-browser screenshot showing the public hostname connection timeout.
- The four surface screenshots are byte-identical evidence copies named for each requested surface; they document the common preflight blocker and do not imply that any surface was successfully reached.

