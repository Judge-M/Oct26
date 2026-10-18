# Operation Silent Ridge — Team 10 defect notes

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Scope: Team 10 live rehearsal, T10/T20 only

## D1 — CTFd question routes fail with HTTP 500

Severity: blocking  
Surface: CTFd `:8083`  
Observed routes: `/silent-ridge`, `/challenges`, and the post-login destination

After signing in, CTFd rendered the visible page `500 — An Internal Server Error has occurred`. The same result persisted after a fresh Team 10 sign-in. No question card, answer field, `Check answer` control, or `Correct` state was rendered.

Impact: 0/8 questions could be reached; 0/8 answers were submitted; 0/8 `Correct` screenshots exist. This matches the route-level failure pattern documented in current rehearsal notes for other participant teams.

Evidence: `screenshots/ctfd-team10-silent-ridge-500.png`, `screenshots/ctfd-team10-post-login-500.png`.

## D2 — CTFd logout link returns 404

Severity: moderate  
Surface: CTFd `:8083`

The visible authenticated `Logout` link led to a page showing `File not found — 404 Not Found`. The session nevertheless became logged out. This is confusing during recovery and makes it difficult to establish a clean participant session.

Evidence: `screenshots/ctfd-logout-404.png`.

## D3 — Shared-host browser session collisions across services

Severity: blocking / session isolation  
Surfaces: IRIS `:8081`, CTFd `:8083`, Guacamole `:8082`, Wazuh `:8443`

The in-app browser used one isolated browser profile, but the services share the public hostname. Switching participant sessions across surfaces caused identity drift and authorization failures: IRIS initially showed another team, later returned `403 Forbidden`, and required re-authentication; Guacamole initially opened another team's desktop; Wazuh initially opened as `team1`. Re-authenticating IRIS restored Team 10 and preserved the server-side T10 claim.

Impact: A participant can unknowingly operate under a different team identity or lose access after authenticating to another surface. The workflow needs separate cookie namespaces per service or separate isolated browser contexts, plus a visible identity check before ticket claims and submissions.

Evidence: `screenshots/iris-queue-forbidden-after-claim.png`, `screenshots/guacamole-team10-desktop-menu.png`, `screenshots/wazuh-team1-permission-error.png`, and final recovery `screenshots/iris-team10-t10-final-queue.png`.

## D4 — Wazuh participant access is unavailable for Team 10

Severity: blocking for T10/T20  
Surface: Wazuh `:8443`

The direct Wazuh surface first opened an existing `team1` session with a visible security permission failure for telemetry search. After logout, the supplied Team 10 login was rejected as invalid. The Guacamole desktop Wazuh shortcut also produced no visible application window.

Impact: The human Wazuh route required by T10 and T20 could not be inspected. The expected answer contracts were documented from the repository matrix, but no live evidence record or live `Correct` receipt was produced.

Evidence: `screenshots/wazuh-team1-permission-error.png`, `screenshots/wazuh-team10-login-error.png`, `screenshots/guacamole-wazuh-launcher-noop.png`.

## D5 — T20 is not claimable in the fresh run

Severity: blocking for requested T20 scope  
Surface: IRIS `:8081`

T20 was absent from the visible IRIS queue after T10 was claimed. The current walkthrough states that T20 requires T07, T09, T11, and T19 to be complete. No T20 claim button was rendered, and no other ticket was claimed as a substitute.

Impact: T20-Q1 through T20-Q4 could not be opened or submitted by Team 10.

Evidence: `screenshots/iris-team10-t10-final-queue.png`.

## Reproduction boundary

These notes describe only the participant-visible rehearsal behavior. No admin surface, controller credential, database, host command, reset, password rotation, commit, or push was used.
