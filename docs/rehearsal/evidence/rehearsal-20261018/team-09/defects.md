# Team 9 rehearsal defect notes

Event: `ridge-oct26-fresh`  
Date: 2026-10-18  
Scope: T09 and T19  
Hostname: `https://desktop-t5pf26o.tail799fee.ts.net`

## D1 — CTFd Silent Ridge route returns HTTP 500

Severity: blocker  
Surface: CTFd `:8083`  
Route: `/silent-ridge`

After successful Team 9 login, the exact documented event route displayed:
`500 — An Internal Server Error has occurred`. The page contained no question
cards or answer fields. This prevented all eight scoped submissions and all
visible `Correct` checks.

Evidence: `screenshots/02-ctfd-event-500.png`.

## D2 — Assigned tickets T09 and T19 were not released

Severity: blocker for this team scope  
Surface: IRIS `:8081`  
Route: `/silent-ridge`

The visible Team 9 queue reported no held ticket and an available list of
T05, T08, T10, T12, T13, T14, T15, T16, T17, and T18. T09 and T19 were absent.
The IRIS native task table showed 15 rows and no T09/T19 rows. Shared progress
was `0 of 20 ticket stages complete`. Per scope, no other ticket was claimed.

Evidence: `screenshots/06-iris-team9-queue-t09-t19-not-available.png`.

## D3 — Shared in-app browser session can expose another team identity

Severity: high  
Surface: IRIS/Guacamole session handling

The initial in-app browser contained pre-existing participant state. Guacamole
opened as `team3` on `desktop-03`, and an IRIS refresh later showed `team-04`
holding T04 even after a Team 9 login had been performed in another tab. The
stale Guacamole session was corrected by using the visible Guacamole logout menu
and logging in again, which opened `desktop-09`. IRIS was likewise re-logged in
as Team 9 before the final queue screenshot.

This is a session-isolation risk for concurrent rehearsal agents: a shared browser
context must not be treated as a team-isolated context.

## D4 — Team desktop has no CSV/text viewer association

Severity: medium  
Surface: Guacamole `:8082/guacamole/` → Team 9 desktop  
Route: `/evidence/server/version-comparison.csv`

Thunar visibly listed `version-comparison.csv`, but opening it produced a “Set
Default Application” dialog with `None available` under Recommended Applications.
The requested human-readable CSV route therefore could not be completed through
the supplied desktop applications.

Evidence: `screenshots/04-guac-csv-open-no-handler.png`.

## D5 — Desktop Web Browser launcher fails

Severity: medium  
Surface: Team 9 desktop Applications menu

The visible Web Browser menu item produced “Failed to execute default Web
Browser. Input/output error.” No command-line workaround was used.

Evidence: `screenshots/05-guac-default-browser-error.png`.

## Counts

- Tickets claimed: 0/2
- Questions submitted: 0/8
- Questions visibly `Correct`: 0/8
- Successful answer screenshots: 0
- Claim screenshots: 0 (neither assigned ticket was available)
- Queue/availability screenshots: 2
- Error screenshots: 3

