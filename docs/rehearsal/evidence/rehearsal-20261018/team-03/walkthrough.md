# Operation Silent Ridge — Team 3 rehearsal walkthrough

Run: `ridge-oct26-fresh`  
Date: 2026-10-18  
Role: Team 3, assigned scope T03 and T13  
Participant hostname: `desktop-t5pf26o.tail799fee.ts.net`  
Surfaces used: IRIS `:8081`, Guacamole `:8082`, CTFd `:8083`

No credentials or secrets are recorded in this walkthrough.

## Outcome

T03 was claimed successfully in IRIS by `team-03`. T13 remained visibly available in the queue, but two claim attempts returned the live error “Ticket unavailable, another team claimed it, or exercise paused.” CTFd login succeeded, but the visible CTFd Team page identified the session as `team1` and the status endpoint identified it as `team-01`, not Team 3. The T03 question route consequently returned “Question unavailable or exercise paused.” No question was submitted and no incorrect-team ticket was claimed.

Successful-answer screenshots do not exist because no answer reached a visible `Correct` result.

## Navigation and claim evidence

1. Opened the isolated in-app browser at the fixed public hostname. No raw IP and no logged-in Chrome session were used.
2. Logged into IRIS and opened **Incident queue**. The page visibly showed `Team: team-03` and `Exercise: running`.
3. Claimed T03. The queue then showed `You hold: T03` and `T03 · active · Owner: team-03`.
   Screenshot: `screenshots/T03-claim-queue.png`.
4. Opened Guacamole and reauthenticated the assigned desktop. The visible desktop title was `desktop-03`.
5. Opened the desktop `Evidence` shortcut. The T03 evidence directory visibly contained `browser/downloads.csv`; the file was identified as a CSV document, but the desktop had no recommended viewer and the browser launcher failed with an I/O error.
   Screenshot: `screenshots/T03-desktop-evidence-viewer-blocked.png`.
6. Navigated to `/evidence/prepared/` for T13. The visible evidence listing contained `windows-process.json`. Its context menu offered no usable viewer; this was captured without opening or modifying the file.
   Screenshots: `screenshots/T13-desktop-evidence-listing.png`, `screenshots/T13-desktop-evidence-viewer-menu.png`.
7. Returned to IRIS. T13 was visibly listed as `available` while T03 remained owned by `team-03`.
   Screenshot: `screenshots/T13-available-queue.png`.
8. Attempted to claim T13 twice, reloading and rechecking the queue between attempts. Both attempts returned the exact visible error “Ticket unavailable, another team claimed it, or exercise paused. Reload the queue.”
   Screenshot: `screenshots/T13-claim-error.png`.

## T03 — Reconstruct the viewer download

Tool and evidence route from the matrix: Autopsy, `/evidence/browser/downloads.csv`.

The Autopsy desktop shortcut was exercised as a human through the desktop. It did not launch a usable application. The supplied evidence file was then located in the read-only Evidence tree, but the desktop had no associated CSV viewer and its Web Browser launcher failed. The prepared matrix and repository walkthrough provide the answer contracts below; none could be entered safely because CTFd resolved the session to Team 1.

### T03-Q1 — What time was the viewer download recorded?

Answer contract: `08:57:00` UTC.

Justification: the first row in the prepared browser-download collection records the viewer download at 08:57:00 UTC. The limitation is collection-scoped: presence in this prepared artifact does not prove every related action.

Result: not submitted; CTFd question route unavailable.

### T03-Q2 — Which executable performed the viewer download?

Answer contract: `brief-viewer.exe`.

Justification: the browser-download record associates the viewer download with the named executable `brief-viewer.exe`; this is a record-level attribution, not proof of all process activity outside the prepared collection.

Result: not submitted; CTFd question route unavailable.

### T03-Q3 — What destination host was recorded?

Answer contract: `briefs.helpdesk.example`.

Justification: the selected download record names `briefs.helpdesk.example` as the destination host. This supports the host recorded for this artifact and does not establish broader communication beyond the specified collection.

Result: not submitted; CTFd question route unavailable.

### T03-Q4 — What local destination directory was recorded?

Answer contract: `C:/Downloads`.

Justification: the selected browser-download record gives `C:/Downloads` as the local destination directory. The result is limited to the prepared browser-download record and should not be generalized to other local paths or activity.

Result: not submitted; CTFd question route unavailable.

## T13 — Inspect acquired process-log records

Tool and evidence route from the matrix: Autopsy, `/evidence/prepared/windows-process.json`.

The desktop evidence tree visibly contained `windows-process.json` under `/evidence/prepared/`. Autopsy did not launch, and the desktop lacked a usable JSON viewer. T13 also could not be claimed: the queue displayed it as available, but the server rejected two claim attempts. Therefore no CTFd T13 question form was reached.

### T13-Q1 — What PID is recorded?

Answer contract: `6364`.

Justification: the prepared process record identifies PID 6364. It is an isolated native training reconstruction and should be interpreted with its acquisition metadata and provenance.

Result: not submitted; T13 claim rejected by IRIS.

### T13-Q2 — Which process name is recorded?

Answer contract: `browser.exe`.

Justification: the prepared process record names the process `browser.exe`; this is the process label in the acquired record and does not replace review of the original provenance or hash.

Result: not submitted; T13 claim rejected by IRIS.

### T13-Q3 — Which host is recorded?

Answer contract: `WS-17`.

Justification: the process record is associated with host `WS-17`. The artifact is an isolated training reconstruction, so the host association must remain bounded by the record’s provenance.

Result: not submitted; T13 claim rejected by IRIS.

### T13-Q4 — What acquisition time is recorded?

Answer contract: `23:22:00` UTC.

Justification: the process record’s acquisition timestamp is 23:22:00 UTC. This is the actual acquisition time in the prepared record, not a replacement for the historical incident timeline.

Result: not submitted; T13 claim rejected by IRIS.

## Screenshot index

- `screenshots/T03-claim-queue.png` — successful T03 IRIS claim and queue state.
- `screenshots/T03-desktop-evidence-viewer-blocked.png` — T03 evidence file and missing viewer route.
- `screenshots/T03-Q1-question-unavailable.png` — CTFd question blocker.
- `screenshots/CTFd-role-mapping-team1.png` — visible CTFd session mapped to `team1`.
- `screenshots/T13-available-queue.png` — T13 visibly available in IRIS.
- `screenshots/T13-claim-error.png` — repeated T13 claim failure state.
- `screenshots/T13-desktop-evidence-listing.png` — T13 prepared evidence listing.
- `screenshots/T13-desktop-evidence-viewer-menu.png` — no usable JSON viewer offered.

