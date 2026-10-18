# Fresh 11-role rehearsal — 2026-10-18

Event: `ridge-oct26-fresh`  
Source release: `caf2da73afa185e040b96de20c3ad4c35d91f9b0`  
Participant hostname: `desktop-t5pf26o.tail799fee.ts.net`  
Browser policy: isolated browser sessions; the user's logged-in Chrome was not used.

## Outcome

The rehearsal covered all ten team scopes and a separate facilitator/admin role. The run produced 25 Markdown walkthrough/defect files and 84 screenshots. No passwords, tokens, or other secrets are included.

The live run did not reach a verified CTFd `Correct` receipt: 0/80 answers were accepted. Six teams successfully claimed one ticket far enough to produce a visible ownership state; the remaining tickets were unavailable, gated, or blocked by cross-surface/session defects.

| Role | Scope | Live result | Evidence |
|---|---|---|---|
| Team 1 | T01, T11 | T01 claimed; T11 gated; 0/8 answers | `team-01/` |
| Team 2 | T02, T12 | T02 held/inspected; T12 unavailable; 0/8 answers | `team-02/` |
| Team 3 | T03, T13 | T03 claimed; T13 claim rejected; 0/8 answers | `team-03/` |
| Team 4 | T04, T14 | T04 claimed; T14 left available; 0/8 answers | `team-04/` |
| Team 5 | T05, T15 | No claim; 0/8 answers | `team-05/` |
| Team 6 | T06, T16 | T06 claimed; T16 unavailable; 0/8 answers | `team-06/` |
| Team 7 | T07, T17 | Browser DNS/routing blocked; 0/8 answers | `team-07/` |
| Team 8 | T08, T18 | No claim; 0/8 answers | `team-08/` |
| Team 9 | T09, T19 | No claim; 0/8 answers | `team-09/` |
| Team 10 | T10, T20 | T10 claimed; T20 gated/unavailable; 0/8 answers | `team-10/` |
| Admin | CTFd, IRIS, Guacamole, Wazuh | Host connection timed out in isolated admin session | `admin/` |

Each team walkthrough records the repository answer contract, the intended human navigation, observed live state, explanation/limitation, and screenshot manifest. Where the service failed before an answer form appeared, the expected answer is explicitly marked as unsubmitted rather than represented as a live success.

## Defects found

1. CTFd `/silent-ridge`, `/challenges`, and post-login routes consistently returned HTTP 500, preventing all answer submissions.
2. Shared hostname cookie/session state caused identity drift between teams across IRIS, CTFd, Guacamole, and Wazuh; separate browser contexts or per-service cookie isolation is needed.
3. CTFd and IRIS account/team mapping was incorrect in the fresh event: Team 3 visibly authenticated as Team 1, and Team 8 was mapped to Team 3.
4. Wazuh participant access failed for multiple teams, and the Guacamole Wazuh launcher was a no-op.
5. Several desktop evidence viewers/launchers (Autopsy and CSV/JSON viewers) were missing or failed to start.
6. IRIS links emitted raw-IP URLs whose certificate did not match the participant hostname.
7. Ticket gating/availability was inconsistent with the running event state: T13/T16/T20 and other assigned tickets were visible as available or expected but returned unavailable or were absent.
8. The isolated admin browser could not route to the Tailscale hostname, so read-only admin checks could not be completed in that session.

## Fix included with this evidence

The CTFd question page had a reproducible HTTP 500. `render_template_string()` returns a plain string, but the route immediately assigned response headers to that value; the resulting `AttributeError` was wrapped by Flask-RESTX and surfaced as a generic 500. The rehearsal branch wraps the rendered page in Flask `make_response()` before applying the cache-control headers. The change is in `integrations/ctfd_silent_ridge/__init__.py` and passed Python byte-compilation plus `git diff --check`.

## Certificate repair performed for this rehearsal

The generated participant certificate covered the server LAN address (`192.168.1.200`) while the rehearsal used the Tailscale address. The event machine was configured with a Tailscale-issued certificate for `desktop-t5pf26o.tail799fee.ts.net`; the original private-CA participant/dashboard files were preserved on the event machine as backups. CTFd, IRIS, Guacamole, and Wazuh were then verified over HTTPS using the public hostname.

## Evidence layout

- `team-01/` through `team-10/`: one folder per team role, with walkthrough, defect notes, and screenshots where available.
- `admin/`: facilitator/admin walkthrough, defect notes, and host-error screenshots.
- Credentials and runtime secrets remain outside the repository.
