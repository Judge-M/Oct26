# Operation Silent Ridge — Team 9 rehearsal walkthrough

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Role: Team 9  
Scope: T09 and T19 (8 questions)  
Participant hostname: `https://desktop-t5pf26o.tail799fee.ts.net`  
Browser: isolated Codex in-app browser session; the user's logged-in Chrome was not used.

## Result

No assigned ticket was claimable during this run. IRIS showed Team 9 with no held
ticket and an available list that did not contain T09 or T19. The IRIS native task
list contained 15 prerequisite tasks and no rows for T09 or T19; shared progress
was visibly `0 of 20 ticket stages complete`.

CTFd authentication succeeded, but the event route
`https://desktop-t5pf26o.tail799fee.ts.net:8083/silent-ridge` returned a visible
`500 An Internal Server Error`. Therefore no question card or answer form could
be reached, and no answer could be submitted or verified as `Correct`.

The Team 9 Guacamole login succeeded and visibly opened `desktop-09`. The
specified T09 evidence route was inspected manually in Thunar. Opening the CSV
produced a visible “Set Default Application” dialog with no recommended
application; the desktop Web Browser launcher then produced a visible “Failed to
execute default Web Browser. Input/output error.” No terminal or command-line
workaround was used.

## Exact answer set and coached routes

These values are transcribed from the requested acceptance matrix and are the
answers to use once the ticket and CTFd question form are available. They were
not submitted in this run because CTFd was unavailable and the tickets were not
released.

### T09 — Compare superseding movement information

Tool: Linux file manager  
Evidence: `/evidence/server/version-comparison.csv`  
Selection: open the CSV in the text viewer  
Limitation: The supplied document or export supports only the stated comparison,
not human receipt or adversary intent.

| Question | Answer | Source |
|---|---|---|
| T09-Q1 | `09:10:00` | `server/version-comparison.csv` |
| T09-Q2 | `BLUE` | `server/version-comparison.csv` |
| T09-Q3 | `10:30-11:30Z` | `server/version-comparison.csv` |
| T09-Q4 | `CEDAR` | `server/version-comparison.csv` |

Human route attempted: Guacamole → Evidence → `server` →
`version-comparison.csv`. Thunar displayed the file and its size, but no text
viewer was installed or associated. The visible failure is documented in the
defect notes and screenshots.

### T19 — Verify the transmitted payload

Tool: Linux file manager  
Evidence: `/evidence/network/dlp-metadata.json`  
Selection: open the metadata and compare its `sha256` with `server/catalog.csv`  
Limitation: The supplied document or export supports only the stated comparison,
not human receipt or adversary intent.

| Question | Answer | Source |
|---|---|---|
| T19-Q1 | `req-72` | `network/dlp-metadata.json` |
| T19-Q2 | `3` | `network/dlp-metadata.json` |
| T19-Q3 | `09:06:00` | `network/dlp-metadata.json` |
| T19-Q4 | `no` | `network/dlp-metadata.json` |

T19 was not claimable, so its dependent evidence comparison was not started.

## IRIS navigation and queue evidence

1. Opened the trusted IRIS hostname at `:8081` and logged in as Team 9.
2. Verified the visible display identity as `team9`; no hyphenated identity was
   required by the visible UI.
3. Opened `/silent-ridge`.
4. Verified the visible queue state: `Team: team-09`, `You hold no ticket`, and
   the available list did not include T09 or T19.
5. Did not claim T04, T05, T08, T10, T12, T13, T14, T15, T16, T17, or T18.
6. Opened the IRIS task list at `/case/tasks?cid=2`; the visible table showed 15
   tasks, including T05, T08, T10, T12–T18, but no T09 or T19.

Queue screenshots:

- `screenshots/01-iris-queue-team9.png`
- `screenshots/06-iris-team9-queue-t09-t19-not-available.png`

## CTFd navigation

1. Opened the trusted CTFd hostname at `:8083` and logged in as Team 9.
2. The exact documented route `/silent-ridge` redirected to a visible CTFd 500
   page after authentication.
3. No answer card, hint, answer field, or `Correct` result was visible.

Error screenshot:

- `screenshots/02-ctfd-event-500.png`

## Guacamole and human evidence inspection

1. The first Guacamole connection was a stale `desktop-03` session showing the
   visible account `team3`. It was explicitly logged out through the Guacamole
   menu.
2. Logged in again with the provided Team 9 participant account. The visible
   connection changed to `desktop-09`.
3. Opened the `Evidence` desktop shortcut and navigated to `/evidence/server/`.
4. Selected `version-comparison.csv` and attempted to open it with the desktop
   file manager. No recommended application was available.
5. Attempted the desktop Web Browser launcher from the visible Applications
   menu. It failed with an I/O error.

Desktop screenshot:

- `screenshots/03-guacamole-team09-desktop.png`

Error screenshots:

- `screenshots/04-guac-csv-open-no-handler.png`
- `screenshots/05-guac-default-browser-error.png`

No files were uploaded, changed, deleted, or executed. No commits or pushes were
made.

