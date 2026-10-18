# Operation Silent Ridge — Team 8 rehearsal walkthrough

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Role: Team 8; requested scope `T08` and `T18` only  
Browser: isolated ChatGPT in-app browser; the user's logged-in Chrome was not used  
Hostname: `https://desktop-t5pf26o.tail799fee.ts.net`

## Result

The run was blocked before a valid Team 8 IRIS queue state could be established.
No ticket was claimed, no evidence item for T08 or T18 was inspected in the
assigned desktop, and no CTFd answer was submitted or verified as `Correct`.

| Count | Result |
|---|---:|
| Tickets in scope | 2 |
| Tickets claimed by Team 8 | 0 |
| Questions in scope | 8 |
| Answers submitted | 0 |
| Visible `Correct` receipts | 0 |
| Questions blocked | 8 |
| Claim/queue screenshots | 1 (wrong-team queue receipt; no valid Team 8 queue reached) |
| Error screenshots | 3 |
| Total screenshots captured | 7 |

## Source contract used

The acceptance matrix and current walkthroughs were read before live work:

- `work/Oct26-rehearsal-20261018/docs/acceptance/question-matrix.md`
- `work/Oct26-rehearsal-20261018/docs/walkthrough/CTF-WALKTHROUGH.md`
- `work/Oct26-rehearsal-20261018/docs/rehearsal/team-03-live-run.md` for the current T08/T18 explanation pattern and route notes

The expected answers below are the documented answer contract only. They are not
live receipts from this run.

## Live navigation and blocker evidence

1. Opened IRIS on the public HTTPS hostname in the isolated browser.
2. Signed out the stale IRIS session that was showing another team.
3. The supplied hyphenated Team 8 IRIS login was rejected with the visible
   `Error: Wrong credentials. Please try again.` message. Screenshot:
   `screenshots/00-iris-login-error.png`.
4. A single fallback attempt using the unhyphenated Team 8-style login did
   authenticate, but the resulting IRIS page identified the user as Team 3,
   showed `You hold: T03`, and showed T08/T18 as available. This session was
   not used to claim or answer anything. Screenshot:
   `screenshots/05-iris-team03-queue-not-team08.png`.
5. CTFd accepted the Team 8 account at `/user` and visibly showed `team8` with
   zero points. Screenshot: `screenshots/06-ctfd-team8-profile.png`.
6. The CTFd login submission rendered `500 — An Internal Server Error has
   occurred`, although the authenticated profile was subsequently reachable.
   Screenshot: `screenshots/02-ctfd-login-500.png`.
7. The CTFd event route `/silent-ridge` rendered the same visible HTTP 500
   page, so the question forms and answer controls never appeared. Screenshot:
   `screenshots/03-ctfd-silent-ridge-500.png`.
8. Guacamole opened an existing desktop session showing `/evidence/prepared/`
   and a file-manager context menu, but no reliable Team 8 identity or Team 8
   connection selector was visible. It was not used as evidence for T08/T18.
   Screenshot: `screenshots/04-guacamole-stale-desktop.png`.

No claim action was attempted from the Team 3 session. No other team's ticket
was touched.

## T08 — Audit document and roster access

Documented route: IRIS → claim T08 → assigned desktop → Autopsy → open
`/evidence/server/access.csv` → inspect the matching request row.

Limitation: Prepared evidence is limited to the specified collection. Presence
of an artifact is not proof of every related action.

### T08-Q1

Expected answer: `plan-v3`  
Explanation: The matching access record identifies the requested resource or
version as `plan-v3`.  
Evidence route: `/evidence/server/access.csv`  
Live status: Blocked before claim and evidence inspection; not submitted; no
`Correct` screenshot.

### T08-Q2

Expected answer: `403`  
Explanation: The matching access record reports an HTTP 403 response.  
Evidence route: `/evidence/server/access.csv`  
Live status: Blocked before claim and evidence inspection; not submitted; no
`Correct` screenshot.

### T08-Q3

Expected answer: `0`  
Explanation: The denied response has zero response-body bytes in the supplied
record.  
Evidence route: `/evidence/server/access.csv`  
Live status: Blocked before claim and evidence inspection; not submitted; no
`Correct` screenshot.

### T08-Q4

Expected answer: `req-75`  
Explanation: The matching access row is identified by request ID `req-75`.  
Evidence route: `/evidence/server/access.csv`  
Live status: Blocked before claim and evidence inspection; not submitted; no
`Correct` screenshot.

## T18 — Follow a small static code example

Documented route: IRIS → claim T18 → assigned desktop → Cutter → open the
harmless training binary at `/evidence/binary/brief-viewer-training` →
Functions → `classify_version`.

Limitation: This harmless training surrogate demonstrates static inspection; it
does not establish the behavior of an acquired incident executable.

### T18-Q1

Expected answer: `3`  
Explanation: The documented `classify_version` example returns version `3` for
the supplied input.  
Evidence route: `/evidence/binary/brief-viewer-training`, Functions →
`classify_version`  
Live status: Blocked before claim and Cutter inspection; not submitted; no
`Correct` screenshot.

### T18-Q2

Expected answer: `cached v3`  
Explanation: The matching branch labels the cached version as `cached v3`.  
Evidence route: `/evidence/binary/brief-viewer-training`, Functions →
`classify_version`  
Live status: Blocked before claim and Cutter inspection; not submitted; no
`Correct` screenshot.

### T18-Q3

Expected answer: `other version`  
Explanation: The alternate branch is labeled `other version`.  
Evidence route: `/evidence/binary/brief-viewer-training`, Functions →
`classify_version`  
Live status: Blocked before claim and Cutter inspection; not submitted; no
`Correct` screenshot.

### T18-Q4

Expected answer: `no`  
Explanation: The static function example does not support an additional
persistence conclusion.  
Evidence route: `/evidence/binary/brief-viewer-training`, Functions →
`classify_version`  
Live status: Blocked before claim and Cutter inspection; not submitted; no
`Correct` screenshot.

## Screenshot manifest

| File | Receipt |
|---|---|
| `screenshots/00-iris-login-error.png` | IRIS rejected the supplied hyphenated Team 8 login. |
| `screenshots/01-iris-wrong-team-identity.png` | IRIS page after the unhyphenated fallback login; the visible identity was not Team 8. |
| `screenshots/02-ctfd-login-500.png` | CTFd login submission rendered HTTP 500. |
| `screenshots/03-ctfd-silent-ridge-500.png` | CTFd question route rendered HTTP 500. |
| `screenshots/04-guacamole-stale-desktop.png` | Existing Guacamole desktop state; not treated as Team 8 evidence. |
| `screenshots/05-iris-team03-queue-not-team08.png` | Queue showed Team 3 holding T03 while T08/T18 were available; no claim made. |
| `screenshots/06-ctfd-team8-profile.png` | CTFd authenticated profile visibly identified Team 8. |

## Credentials handling

No password, token, or other secret is included in this walkthrough or the
defect notes.
