# Team 3 live rehearsal — Operation Silent Ridge

This is the sanitized, human-driven browser rehearsal record for Team 3. It
contains answer values and navigation notes, but no passwords, private runtime
configuration, live rosters, or database exports.

**Run date:** 2026-10-18  
**Participant surfaces:** CTFd (`:8083`) and IRIS (`:8081`) over the participant
TLS endpoint  
**Team accounts tested:** CTFd `team-03-p01`; IRIS `team-03`  
**Reference:** [`question-matrix.md`](../acceptance/question-matrix.md)

## Result at the time of capture

Team 3 completed 64 live submissions across T03 and T04 through T18. Every
submission returned the CTFd success message and earned a point. The remaining
ticket stages were shared-state dependent: T01 was still owned by Team 1, T02
was already complete, and T19/T20 were locked behind the shared dependency
chain. Those tickets are included below with their complete walkthrough values;
they must not be stolen or reset while another team is using the cooperative
queue.

The Team 3 accounts were tested with fresh browser sign-ins after the rehearsal
runtime had drifted from the supplied handout. Both logins succeeded. No
credential value is recorded here.

## Human workflow

1. Open CTFd and IRIS in the participant browser. The private participant
   certificate required an explicit browser exception for this rehearsal; the
   browser was not the user's logged-in personal session.
2. Sign in as the Team 3 CTFd participant and the Team 3 IRIS participant.
3. In IRIS, read the queue and claim an available ticket. The ticket owner and
   the `You hold` banner are the authoritative claim evidence.
4. Read the ticket's coached tool, evidence path, query, and limitation. The
   answers below are bounded observations, not claims about intent or missing
   telemetry.
5. In CTFd, open the question, enter the value, click **Check answer**, and
   verify the visible **Correct** result. Each completed Team 3 question has a
   screenshot in [`evidence/`](evidence/).
6. Return to IRIS and confirm that the shared finding/synchronization state is
   visible before moving to the next ticket.

## Ticket status and evidence

| Ticket | Shared status | Team 3 evidence |
|---|---|---|
| T01 | Active, owned by Team 1 at capture | Shared dependency; no Team 3 claim |
| T02 | Complete before Team 3 run | Shared completion; no Team 3 claim |
| T03 | Complete by Team 3 | 4 screenshots |
| T04 | Complete by Team 3 | 4 screenshots |
| T05 | Complete by Team 3 | 4 screenshots |
| T06 | Complete by Team 3 | 4 screenshots |
| T07 | Complete by Team 3 | 4 screenshots |
| T08 | Complete by Team 3 | 4 screenshots |
| T09 | Complete by Team 3 | 4 screenshots |
| T10 | Complete by Team 3 | 4 screenshots |
| T11 | Complete by Team 3 | 4 screenshots |
| T12 | Complete by Team 3 | 4 screenshots |
| T13 | Complete by Team 3 | 4 screenshots |
| T14 | Complete by Team 3 | 4 screenshots |
| T15 | Complete by Team 3 | 4 screenshots |
| T16 | Complete by Team 3 | 4 screenshots |
| T17 | Complete by Team 3 | 4 screenshots |
| T18 | Complete by Team 3 | 4 screenshots |
| T19 | Locked at capture; waits for T01 | Pending shared dependency |
| T20 | Locked at capture; waits for T19 | Pending shared dependency |

## Complete 80-question walkthrough

Each row says what a human reads, what value is entered, and why that value is
the defensible answer. For live Team 3 rows, the screenshot link points to the
post-submit browser state.

### T01 — Wireshark / network sensor capture

Open `/evidence/network/sensor.pcap` in Wireshark and use `udp.port == 514`.
Read the matching packet fields; the capture is replayed/reconstructed, so it
does not prove human receipt, reading, or intent.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T01-Q1 | `WS-17` | The filtered sensor record identifies the source host as WS-17. |
| T01-Q2 | `req-71` | The same filtered exchange carries request identifier req-71. |
| T01-Q3 | `req-72` | The adjacent matching exchange carries request identifier req-72. |
| T01-Q4 | `198.51.100.77` | The destination field is the documented training address. |

### T02 — Wireshark / DNS capture

Open `/evidence/network/dns.pcap` and use the `dns` display filter. Read the
answer records; DNS evidence identifies lookups and responses, not successful
human use or intent.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T02-Q1 | `relay.archive.example` | The DNS answer names the archive relay. |
| T02-Q2 | `198.51.100.77` | The relay name resolves to the documented training address. |
| T02-Q3 | `10.26.10.17` | The internal name record resolves to 10.26.10.17. |
| T02-Q4 | `60` | The record's TTL field is 60 seconds. |

### T03 — Autopsy / browser downloads

In Autopsy open `/evidence/browser/downloads.csv` and inspect the browser
download rows. The collection proves the listed artifact fields only; presence
does not prove every related action.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T03-Q1 | `08:57:00` | The download timestamp is the first row's recorded time. [Live evidence](evidence/T03-Q1-correct.jpg) |
| T03-Q2 | `brief-viewer.exe` | The downloaded filename is brief-viewer.exe. [Live evidence](evidence/T03-Q2-correct.jpg) |
| T03-Q3 | `briefs.helpdesk.example` | The source URL host is briefs.helpdesk.example. [Live evidence](evidence/T03-Q3-correct.jpg) |
| T03-Q4 | `C:/Downloads` | The destination path is C:/Downloads. [Live evidence](evidence/T03-Q4-correct.jpg) |

### T04 — Autopsy / endpoint events

In Autopsy open `/evidence/endpoint/events.csv` and inspect the event row for
the viewer. The prepared collection is limited to the supplied endpoint export.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T04-Q1 | `BriefSync` | The event's product/application field is BriefSync. [Live evidence](evidence/T04-Q1-correct.jpg) |
| T04-Q2 | `brief-viewer.exe` | The process/image field names brief-viewer.exe. [Live evidence](evidence/T04-Q2-correct.jpg) |
| T04-Q3 | `user logon` | The event type is recorded as user logon. [Live evidence](evidence/T04-Q3-correct.jpg) |
| T04-Q4 | `09:08:00` | The endpoint event timestamp is 09:08:00. [Live evidence](evidence/T04-Q4-correct.jpg) |

### T05 — Autopsy / deleted disk artifact

In Autopsy open `/evidence/disk/WS17-fat16.img`, choose **Deleted Files**, and
inspect the entry ending `OVECACH.TXT`. The prepared image supplies the artifact
content but does not establish every related action.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T05-Q1 | `LANTERN` | The artifact's operation field names LANTERN. [Live evidence](evidence/T05-Q1-correct.jpg) |
| T05-Q2 | `3` | The artifact records version/sequence 3. [Live evidence](evidence/T05-Q2-correct.jpg) |
| T05-Q3 | `AMBER` | The artifact's older route marker is AMBER. [Live evidence](evidence/T05-Q3-correct.jpg) |
| T05-Q4 | `CEDAR` | The replacement route marker is CEDAR. [Live evidence](evidence/T05-Q4-correct.jpg) |

### T06 — Wazuh / session identity

In Wazuh search `/evidence/wazuh/telemetry.jsonl` for
`data.session:S-41`. Historical replay is not a live observation; missing
telemetry is not proof that an event did not occur.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T06-Q1 | `m.ellis` | Session S-41 is associated with m.ellis. [Live evidence](evidence/T06-Q1-correct.jpg) |
| T06-Q2 | `09:03:00` | The session record begins at 09:03:00. [Live evidence](evidence/T06-Q2-correct.jpg) |
| T06-Q3 | `previous_claim` | The refresh reason/action is previous_claim. [Live evidence](evidence/T06-Q3-correct.jpg) |
| T06-Q4 | `no` | No MFA event is recorded in this selected telemetry record. [Live evidence](evidence/T06-Q4-correct.jpg) |

### T07 — Wazuh / password-reset effect

In Wazuh search `data.action:session_refresh`. Compare the two refresh records
and preserve the session-revocation limitation.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T07-Q1 | `09:20:00` | The password-reset-related refresh is timestamped 09:20:00. [Live evidence](evidence/T07-Q1-correct.jpg) |
| T07-Q2 | `09:26:00` | The later refresh is timestamped 09:26:00. [Live evidence](evidence/T07-Q2-correct.jpg) |
| T07-Q3 | `S-41` | Both records refer back to session S-41. [Live evidence](evidence/T07-Q3-correct.jpg) |
| T07-Q4 | `session revocation` | The later record states the session-revocation outcome. [Live evidence](evidence/T07-Q4-correct.jpg) |

### T08 — Autopsy / server access export

In Autopsy open `/evidence/server/access.csv` and inspect the matching request
row. The CSV supports the recorded request only, not intent.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T08-Q1 | `plan-v3` | The requested resource/version is plan-v3. [Live evidence](evidence/T08-Q1-correct.jpg) |
| T08-Q2 | `403` | The response status is 403. [Live evidence](evidence/T08-Q2-correct.jpg) |
| T08-Q3 | `0` | The response body/bytes field is 0. [Live evidence](evidence/T08-Q3-correct.jpg) |
| T08-Q4 | `req-75` | The request identifier is req-75. [Live evidence](evidence/T08-Q4-correct.jpg) |

### T09 — Linux file manager / version comparison

Open `/evidence/server/version-comparison.csv` in the text viewer and compare
the listed versions and route window. The export supports only this comparison.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T09-Q1 | `09:10:00` | The comparison record's timestamp is 09:10:00. [Live evidence](evidence/T09-Q1-correct.jpg) |
| T09-Q2 | `BLUE` | The older version/route marker is BLUE. [Live evidence](evidence/T09-Q2-correct.jpg) |
| T09-Q3 | `10:30-11:30Z` | The permitted comparison window is 10:30-11:30Z. [Live evidence](evidence/T09-Q3-correct.jpg) |
| T09-Q4 | `CEDAR` | The replacement route is CEDAR. [Live evidence](evidence/T09-Q4-correct.jpg) |

### T10 — Wazuh / WS-22 process record

In Wazuh search `data.host:WS-22` and read the matching process event. This is
historical replay and has the same missing-telemetry limitation.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T10-Q1 | `WS-22` | The telemetry host field is WS-22. [Live evidence](evidence/T10-Q1-correct.jpg) |
| T10-Q2 | `Exercise IT` | The user/owner field is Exercise IT. [Live evidence](evidence/T10-Q2-correct.jpg) |
| T10-Q3 | `C:/Program Files/Approved/briefsync.exe` | The executable path is the approved BriefSync path. [Live evidence](evidence/T10-Q3-correct.jpg) |
| T10-Q4 | `r.chen` | The event's account field is r.chen. [Live evidence](evidence/T10-Q4-correct.jpg) |

### T11 — Wazuh / WS-31 process record

In Wazuh search `data.host:WS-31` and read the process start/stop fields.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T11-Q1 | `BriefSync` | The application field is BriefSync. [Live evidence](evidence/T11-Q1-correct.jpg) |
| T11-Q2 | `08:45:00` | The start time is 08:45:00. [Live evidence](evidence/T11-Q2-correct.jpg) |
| T11-Q3 | `08:50:00` | The end time is 08:50:00. [Live evidence](evidence/T11-Q3-correct.jpg) |
| T11-Q4 | `no` | No corresponding external transfer is present in this record. [Live evidence](evidence/T11-Q4-correct.jpg) |

### T12 — Wazuh / coverage event

In Wazuh search `data.type:coverage` and read the coverage record. It is a
historical replay rather than a live sensor observation.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T12-Q1 | `WS-31` | The coverage record names WS-31. [Live evidence](evidence/T12-Q1-correct.jpg) |
| T12-Q2 | `09:14:00` | Coverage begins at 09:14:00. [Live evidence](evidence/T12-Q2-correct.jpg) |
| T12-Q3 | `09:18:00` | Coverage ends at 09:18:00. [Live evidence](evidence/T12-Q3-correct.jpg) |
| T12-Q4 | `120` | The duration field is 120 seconds. [Live evidence](evidence/T12-Q4-correct.jpg) |

### T13 — Autopsy / prepared Windows process record

In Autopsy open `/evidence/prepared/windows-process.json`. This is an isolated
training reconstruction with acquisition UTC; it does not replace the
historical incident timeline.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T13-Q1 | `6364` | The process record's PID is 6364. [Live evidence](evidence/T13-Q1-correct.jpg) |
| T13-Q2 | `browser.exe` | The process image is browser.exe. [Live evidence](evidence/T13-Q2-correct.jpg) |
| T13-Q3 | `WS-17` | The record identifies host WS-17. [Live evidence](evidence/T13-Q3-correct.jpg) |
| T13-Q4 | `23:22:00` | The process timestamp is 23:22:00. [Live evidence](evidence/T13-Q4-correct.jpg) |

### T14 — Autopsy / prepared scheduled task record

In Autopsy open `/evidence/prepared/windows-task.json` and inspect the task
fields. Treat it as a bounded reconstruction, not a complete historical claim.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T14-Q1 | `BriefSync` | The task name is BriefSync. [Live evidence](evidence/T14-Q1-correct.jpg) |
| T14-Q2 | `brief-viewer.exe` | The task action invokes brief-viewer.exe. [Live evidence](evidence/T14-Q2-correct.jpg) |
| T14-Q3 | `23:22:01` | The task timestamp is 23:22:01. [Live evidence](evidence/T14-Q3-correct.jpg) |
| T14-Q4 | `no` | The task record does not show the requested external-transfer field. [Live evidence](evidence/T14-Q4-correct.jpg) |

### T15 — Autopsy / prepared memory process list

In Autopsy open `/evidence/prepared/memory-processes.json` and inspect the
process and command-line fields. Preserve the reconstruction provenance.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T15-Q1 | `6364` | The relevant process PID is 6364. [Live evidence](evidence/T15-Q1-correct.jpg) |
| T15-Q2 | `7644` | The second related process PID is 7644. [Live evidence](evidence/T15-Q2-correct.jpg) |
| T15-Q3 | `browser.exe` | The process image is browser.exe. [Live evidence](evidence/T15-Q3-correct.jpg) |
| T15-Q4 | `C:/Temp/move-cache.txt` | The command-line/cache path is C:/Temp/move-cache.txt. [Live evidence](evidence/T15-Q4-correct.jpg) |

### T16 — Autopsy / prepared Windows connections

In Autopsy open `/evidence/prepared/windows-connections.json` and inspect the
connection row. This proves the reconstructed connection fields only.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T16-Q1 | `6364` | The connection belongs to PID 6364. [Live evidence](evidence/T16-Q1-correct.jpg) |
| T16-Q2 | `198.51.100.77` | The remote address is 198.51.100.77. [Live evidence](evidence/T16-Q2-correct.jpg) |
| T16-Q3 | `443` | The remote port is 443. [Live evidence](evidence/T16-Q3-correct.jpg) |
| T16-Q4 | `no` | No additional transfer flag is recorded in the row. [Live evidence](evidence/T16-Q4-correct.jpg) |

### T17 — Cutter / training binary strings

Open `/evidence/binary/brief-viewer-training` in Cutter and inspect
**Windows > Strings**. This harmless training surrogate demonstrates static
inspection and is not evidence about an acquired incident executable.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T17-Q1 | `198.51.100.77` | The training binary contains the documented address string. [Live evidence](evidence/T17-Q1-correct.jpg) |
| T17-Q2 | `/upload` | The training binary contains the `/upload` path string. [Live evidence](evidence/T17-Q2-correct.jpg) |
| T17-Q3 | `BriefSync` | The product marker appears in the string table. [Live evidence](evidence/T17-Q3-correct.jpg) |
| T17-Q4 | `no` | No additional host marker is present in the selected string result. [Live evidence](evidence/T17-Q4-correct.jpg) |

### T18 — Cutter / training binary function

Open the same training binary in Cutter and inspect **Functions >
classify_version**. The function result is a static training demonstration.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T18-Q1 | `3` | classify_version returns version 3 for the supplied input. [Live evidence](evidence/T18-Q1-correct.jpg) |
| T18-Q2 | `cached v3` | The cached-v3 branch is the matching classification. [Live evidence](evidence/T18-Q2-correct.jpg) |
| T18-Q3 | `other version` | The alternate branch is labeled other version. [Live evidence](evidence/T18-Q3-correct.jpg) |
| T18-Q4 | `no` | No additional persistence conclusion follows from this function. [Live evidence](evidence/T18-Q4-correct.jpg) |

### T19 — Linux file manager / DLP metadata

After T01 releases the dependency, open `/evidence/network/dlp-metadata.json` in
the Linux file manager's text viewer and compare its sha256 with
`server/catalog.csv`. The supplied documents support only the comparison.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T19-Q1 | `req-72` | The metadata record is keyed to req-72. |
| T19-Q2 | `3` | The metadata records version 3. |
| T19-Q3 | `09:06:00` | The metadata timestamp is 09:06:00. |
| T19-Q4 | `no` | The comparison does not establish human receipt or intent. |

### T20 — Wazuh / request correlation

After T19 completes, search Wazuh for `data.request:req-72`. Historical replay
supports the listed correlation only; missing telemetry is not proof of absence.

| Question | Answer | Explanation / evidence |
|---|---|---|
| T20-Q1 | `3` | The req-72 telemetry record attributes version 3. |
| T20-Q2 | `no` | No positive receipt flag is present in the selected record. |
| T20-Q3 | `no` | No additional transfer flag is present in the selected record. |
| T20-Q4 | `no` | The record does not establish human intent. |

## Issues found during the rehearsal

### CTFd active-question rendering

The default `/silent-ridge` page intermittently rendered the Team 3 ownership
banner but omitted the current active question forms. Opening the same page with
the explicit `?question=Txx-Qy` query rendered the expected form and allowed a
normal human answer submission. This was reproducible across several claimed
tickets. It is a real usability defect: the default page should render the
active ticket's questions or provide an unambiguous link to them. The direct
question route was used only as a documented workaround while preserving the
normal submit/check-answer flow. The repository fix adds `no-store` and
`Vary: Cookie` headers to the CTFd question response so a pre-claim page cannot
be reused after a claim; it is committed and pushed on this rehearsal branch.

### Participant certificate warning

The participant certificate is private-CA issued and does not cover every
address used to reach the rehearsal host. A browser exception was required for
the authorized rehearsal. Production/event deployment should distribute the
participant CA and use a hostname/SAN that matches the published endpoint;
silently teaching participants to ignore certificate warnings is not an
acceptable event-day fix.

### Password drift

The repo intentionally does not publish credentials. The live CTFd and IRIS
Team 3 accounts had drifted from the supplied rehearsal handout. The two Team 3
accounts were reset in the runtime and then verified with fresh browser logins.
The SSH administrator credential was not changed.

### Service health

The live answer flow returned CTFd success responses for all 64 Team 3
submissions captured here. The integration and CTFd logs showed successful
requests and no answer-processing error during the pass. The shared state must
still be rechecked after Team 1 completes T01 and before claiming T19/T20.

