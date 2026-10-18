# Team 3 rehearsal defects and blockers

## Blocking defects

1. **CTFd role mapping is wrong for the supplied Team 3 login.** The visible CTFd Team page shows `team1`, with members `team1`, `team1-p02`, and `team1-p03`. The authenticated `/silent-ridge/status` response also reports `team: team-01`. IRIS simultaneously shows `team-03`. This prevents safe Team 3 answer submission because the CTFd session is attached to another team.
2. **CTFd question route is unavailable.** Opening the explicit coached route for `T03-Q1` returned “Question unavailable or exercise paused. Return to the incident queue.” The event status endpoint reported `mode: running`, so the message does not match the visible event state.
3. **IRIS T13 claim is rejected while the queue says available.** The queue displayed T13 as `available` twice after reload. Two human claim attempts returned “Ticket unavailable, another team claimed it, or exercise paused.” T13 remained available after reauthentication, so the UI state and claim endpoint disagree.

## Evidence/tool defects

4. **Autopsy desktop shortcut did not launch a usable application.** The shortcut was exercised from the assigned `desktop-03` session; no investigation window became available.
5. **Desktop evidence viewer is incomplete.** `/evidence/browser/downloads.csv` and `/evidence/prepared/windows-process.json` were visible in Thunar, but no recommended viewer was installed/associated. The default browser launcher produced an input/output error, and the Open With dialog offered no suitable CSV/JSON viewer. No file was changed.

## Scope and safety notes

- The rehearsal used the isolated in-app browser and the fixed public hostname. The user’s logged-in Chrome was not used.
- No raw-IP navigation was used for the live participant surfaces.
- No credentials, passwords, or secrets are included in this folder.
- No other team’s ticket was claimed, no answer was submitted, and no event configuration or data was changed.
- No commits or pushes were made.

