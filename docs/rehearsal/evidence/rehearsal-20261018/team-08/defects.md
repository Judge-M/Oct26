# Operation Silent Ridge — Team 8 defect notes

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Scope: T08 and T18 only

## D1 — IRIS Team 8 account is unavailable or mis-mapped

Observed in the isolated browser on the public HTTPS hostname:

- The supplied hyphenated Team 8 IRIS login returned the visible wrong-
  credentials error. Receipt: `screenshots/00-iris-login-error.png`.
- A fallback Team 8-style login was accepted, but the resulting event queue
  identified the session as Team 3, showed `You hold: T03`, and offered T08 and
  T18 as available. Receipt: `screenshots/05-iris-team03-queue-not-team08.png`.

Impact: Team 8 could not establish a valid IRIS identity and therefore could
not claim T08 or T18 without violating the scope rule. No claim was attempted
from the misidentified session.

Suggested follow-up: reconcile the live IRIS account inventory and event-team
mapping for Team 8 before the next rehearsal. Verify the login-to-team mapping
from the queue's displayed identity, not from login success alone.

## D2 — CTFd login redirect and event route return HTTP 500

Observed:

- Submitting the CTFd login form rendered the visible 500 page. Receipt:
  `screenshots/02-ctfd-login-500.png`.
- A direct visit to `/user` afterward showed the authenticated Team 8 profile,
  so the session was created despite the failed redirect.
- A direct visit to `/silent-ridge` rendered the visible 500 page. Receipt:
  `screenshots/03-ctfd-silent-ridge-500.png`.

Impact: The question page never rendered, so no answer form, submission, or
visible `Correct` receipt was available. This blocked all eight in-scope
questions even though CTFd recognized Team 8.

Suggested follow-up: inspect the server-side exception for the login redirect
and `/silent-ridge` handler on the fresh event deployment. Do not infer that
the event is healthy from `/user` alone; the question route must render for the
claimed ticket.

## D3 — Guacamole opened an existing, non-identifying desktop state

Observed: Guacamole connected directly to a desktop showing a file manager at
`/evidence/prepared/`, with no visible Team 8 label or connection selector. The
state was treated as stale/ambiguous and was not used to claim evidence for
T08/T18. Receipt: `screenshots/04-guacamole-stale-desktop.png`.

Impact: Evidence inspection could not be safely attributed to Team 8. No
Autopsy or Cutter result was used as a live receipt.

Suggested follow-up: ensure a fresh Guacamole session opens the Team 8
connection explicitly, or expose the connection/team identity in the session
header before participants inspect evidence.

## Run accounting

- Completion: 0 of 8 questions.
- Blocked: 8 of 8 questions.
- Tickets claimed: 0 of 2.
- Wrong-team claims: 0.
- Visible `Correct` receipts: 0.
- Error screenshots: 3.
- Total screenshots: 7.
