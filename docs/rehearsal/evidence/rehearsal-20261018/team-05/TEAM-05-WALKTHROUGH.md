# Operation Silent Ridge — Team 5 rehearsal walkthrough

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Role: Team 5 (`T05` and `T15`)  
Browser: isolated ChatGPT in-app browser, fixed public hostname

## Scope and source contract

The repository acceptance matrix and current walkthrough identify eight questions:

| Question | Expected answer | Human investigation route | Explanation / limitation |
|---|---|---|---|
| T05-Q1 | `LANTERN` | IRIS → claim T05 → assigned desktop → Autopsy → open `/evidence/disk/WS17-fat16.img` → Deleted Files → inspect the entry ending `OVECACH.TXT` | Read the recovered entry’s requested value. The prepared collection supports the artifact only; it does not prove every related action. |
| T05-Q2 | `3` | Same T05 Autopsy entry | Read the requested count/value from the same recovered entry; keep the conclusion bounded to the supplied collection. |
| T05-Q3 | `AMBER` | Same T05 Autopsy entry | Read the requested field from the recovered entry; do not infer activity beyond the artifact. |
| T05-Q4 | `CEDAR` | Same T05 Autopsy entry | Read the requested field from the recovered entry; do not infer activity beyond the artifact. |
| T15-Q1 | `6364` | IRIS → claim T15 → assigned desktop → Autopsy → open `/evidence/prepared/memory-processes.json` | Identify the requested process ID in the prepared native-training reconstruction. It does not replace the historical incident timeline; consult provenance and the original hash. |
| T15-Q2 | `7644` | Same prepared memory-processes record | Identify the requested parent/process relationship from the supplied reconstruction; do not extend it into an unsupported historical claim. |
| T15-Q3 | `browser.exe` | Same prepared memory-processes record | Read the requested process name from the record; keep the conclusion limited to the prepared collection. |
| T15-Q4 | `C:/Temp/move-cache.txt` | Same prepared memory-processes record | Read the requested command/path value from the record; do not infer execution or intent beyond the supplied reconstruction. |

The expected values above are the repository answer contract, not live submission receipts.

## Intended human navigation and evidence capture

1. In IRIS, sign in as `team-05`, open Incident queue, and claim only T05 or T15. Capture the queue before claiming and the claimed-ticket state after claiming.
2. In the team desktop, open Autopsy and inspect the named evidence path. The evidence is read-only; no binary is to be executed.
3. In CTFd, open Questions and help for the claimed ticket, read the answer-format line, enter only the requested value, and submit one question at a time.
4. After each submission, verify the visible `Correct` result and capture the page. Record the question, observed evidence route, answer justification, limitation, and screenshot filename.
5. After the final answer, verify the ticket/finding state in IRIS and capture the queue/finding state. Do not claim another team’s ticket.

## Live execution status

The fixed public hostname loaded in the isolated browser. The supplied unhyphenated Team 5 account was accepted by IRIS, but IRIS showed only `#1 - Initial Demo` and returned `Access denied to #1`; the dashboard contained no attributed tasks. The hyphenated role name supplied for IRIS was rejected by the live login form. This prevented claiming T05 or T15.

The isolated CTFd navigation repeatedly timed out while opening the fixed-host login URL, leaving blank tabs. No CTFd login, question form, answer submission, or live `Correct` receipt was reached.

Guacamole login succeeded for Team 5 and displayed `desktop-05`. The desktop showed the expected Autopsy, Cutter, Wireshark, Wazuh, Questions and help, Incident queue, How-to guides, and Evidence shortcuts. Attempts to launch the Autopsy and Questions and help shortcuts produced no application window, so no live evidence record was inspected. No ticket was claimed, so the evidence work was not continued outside the required claim flow.

## Screenshot manifest

| File | What it proves |
|---|---|
| `iris-team5-access-denied.png` | Live IRIS session as `team5`; case banner says `Access denied to #1`, with zero attributed open tasks. |
| `iris-authentication-required.png` | Stale/cross-tab IRIS state showing an authentication-required error; retained as a session-isolation defect receipt. |
| `guacamole-team05-desktop.png` | Team 5 Guacamole session after login, showing the desktop tool/shortcut layout. |

There are no successful claim/queue or CTFd `Correct` screenshots because those states were not reached.

## Credentials handling

No password, token, or secret is included in this walkthrough.
