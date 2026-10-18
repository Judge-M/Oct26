# Team 7 rehearsal defects

## DEF-001 — isolated browser cannot reach participant hostname

- Status: blocking
- Scope: `ridge-oct26-fresh`
- Observed: The isolated in-app browser was able to load a public HTTPS page,
  but navigation to the supplied participant hostname on the CTFd port timed
  out before a document or login form appeared. The same failure prevented
  access to IRIS, Guacamole, and Wazuh.
- Isolation check: The user's logged-in Chrome was not used. A separate Edge
  launch was attempted, but no Edge window became available for interaction.
- Host-side evidence: A read-only connectivity check from the Windows host
  resolved the hostname through Tailscale and reported the CTFd TCP port as
  reachable. This confirms the rehearsal endpoint is not proven down; it
  indicates a routing/DNS boundary between the isolated browser runtime and the
  host's Tailscale interface.
- Impact: 0 tickets claimed, 0 of 8 answers submitted, 0 visible `Correct`
  receipts, and 0 required screenshots.
- Suggested retry: provide an isolated browser/session with access to the
  host's Tailscale DNS and route, or provide an equivalent isolated browser
  endpoint that can reach the same publicly trusted HTTPS hostname. Do not use
  the user's logged-in Chrome and do not bypass HTTPS validation.

## Counts

- Blockers: 1
- Non-blocking defects: 0
- Tickets claimed: 0 / 2
- Answers submitted: 0 / 8
- Correct receipts verified: 0 / 8
- Screenshots created: 0
