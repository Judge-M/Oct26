# Operation Silent Ridge — Team 1 defects and blockers

No credentials or secrets are included in this file.

## D1 — CTFd assigned route returns 500

- Surface: CTFd on the public tailnet hostname, `/silent-ridge`.
- Reproduction: authenticate as the Team 1 participant, then open the assigned
  Questions route.
- Observed: a page headed `500` with `An Internal Server Error has occurred`.
- Evidence: `13-ctfd-silent-ridge-500-blocker.png`.
- Impact: all four T01 and all four T11 questions could not be submitted, so no
  live `Correct` result or answer screenshot exists.
- Scope note: an alternate stale tab showed `403 Forbidden` for the same route;
  the fresh authenticated attempt reproduced the 500.

## D2 — IRIS participant links still advertise the raw service host

- Surface: IRIS Operation Silent Ridge queue.
- Observed: the visible `Questions and help`, `Scoreboard`, and shared-task
  links expose `192.168.1.200` values even though the public participant
  hostname is `desktop-t5pf26o.tail799fee.ts.net`.
- Impact: following the rendered link can leave the supported public TLS path
  and may recreate the certificate/routing failure that the rehearsal was meant
  to avoid.
- Evidence: visible IRIS queue captures, especially
  `16-iris-team01-t01-claim-top.png` and `15-iris-team01-t01-held-t11-absent.png`.

## D3 — T11 dependency remained unavailable

- Surface: IRIS queue.
- Observed: T10 was available, while T11 was absent. Reload/retry did not
  change the queue.
- Impact: Team 1 could not claim T11 without claiming another ticket, which was
  explicitly out of scope.
- Classification: expected exercise gating unless T10 has already completed
  elsewhere; it is an exact blocker for this run, not a permission to bypass
  the dependency.
- Evidence: `15-iris-team01-t01-held-t11-absent.png` and the queue accessibility
  state recorded during the run.

## D4 — Wazuh coached query does not narrow cleanly

- Surface: Wazuh Discover.
- Observed: the seven-day `silent-ridge-*` view showed 498 hits. Entering
  `data.host:WS-31` showed 262 hits, but visible rows included other hosts; the
  UI also emitted a Lucene/DQL warning and repeated `Request failed with status
  code: 403` notices for UI settings.
- Impact: the historical WS-31 values could not be visually verified through a
  clean filtered result in this run. I did not treat the mixed result set as
  proof.
- Evidence: `05-wazuh-discover-498-hits-range.png` and
  `06-wazuh-ws31-query-262-hits.png`.

## D5 — Guacamole Wazuh shortcut did not launch

- Surface: Team 1 Guacamole desktop.
- Observed: the Wazuh desktop shortcut could be selected but did not open the
  application. The separate Wazuh browser surface was reachable and used for
  the read-only inspection.
- Impact: desktop-only Wazuh navigation was unavailable; the browser surface
  provided the fallback evidence route.
- Evidence: `03-guacamole-team-01-desktop.png` plus the browser-run Wazuh
  captures.

## D6 — IRIS session identity was unstable during retry

- Surface: IRIS public hostname.
- Observed: after a successful Team 1 queue view, a later reload returned 401;
  a subsequent login navigation redirected to a dashboard labeled for a
  different team and showed access denied to the case. No other ticket was
  claimed and the earlier verified Team 1 T01 claim was preserved in the
  screenshots.
- Impact: further queue retries were stopped to avoid acting under the wrong
  team identity.
- Evidence: the stable Team 1 claim capture is `16-iris-team01-t01-claim-top.png`;
  the later unauthorized state was observed in-browser but not used as positive
  Team 1 evidence.
