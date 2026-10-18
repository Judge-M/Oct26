# Operation Silent Ridge — Team 1 walkthrough

Event: `ridge-oct26-fresh`  
Scope: T01 and T11 only  
Browser: isolated Codex in-app browser, using the public tailnet hostname
`desktop-t5pf26o.tail799fee.ts.net`.

## Result

T01 was claimed by Team 1 and its coached Wireshark evidence was inspected. T11
was not claimable during this run: the queue exposed T10 as available and did
not expose T11, consistent with the documented T10 → T11 prerequisite. No
question reached a verified CTFd `Correct` result because the CTFd ticket route
returned a visible server error after authentication. Therefore the run has
0/8 verified submissions; the values below are the documented expected values,
not claims that they were accepted live.

## Evidence index

| File | What it shows |
|---|---|
| `01-iris-t01-claimed-queue.png` | Initial T01 claim/queue capture |
| `02-iris-t01-claimed-after-relogin.png` | T01 still held after an IRIS sign-in |
| `03-guacamole-team-01-desktop.png` | Team 1 Guacamole desktop and evidence-tool shortcuts |
| `04-wireshark-t01-req72-destination.png` | Wireshark filtered capture with the req-72 transfer and destination |
| `05-wazuh-discover-498-hits-range.png` | Wazuh Discover on `silent-ridge-*`, seven-day range, 498 hits |
| `06-wazuh-ws31-query-262-hits.png` | Wazuh query text `data.host:WS-31` and the resulting visible state |
| `10-iris-team01-t01-claimed-queue.png` | T01 held in the IRIS queue |
| `11-iris-team01-t01-claim-visible.png` | T01 owner/claim state |
| `13-ctfd-silent-ridge-500-blocker.png` | CTFd `/silent-ridge` visible 500 error |
| `15-iris-team01-t01-held-t11-absent.png` | Queue state around the claimed ticket; T11 was absent |
| `16-iris-team01-t01-claim-top.png` | Clear T01 claim evidence: owner `team-01`, relinquish control, and question link |

## Human navigation and observations

1. Opened IRIS at the public `:8081` hostname and entered the Operation Silent
   Ridge queue. The queue showed `Team: team-01`, `You hold: T01`, and T01 as
   `Wireshark · active · Owner: team-01`. Screenshot: `16-iris-team01-t01-claim-top.png`.
2. Did not claim another ticket. T11 was not listed. T10 was still shown as
   available, so the documented prerequisite had not completed. This is an
   exact dependency blocker, not a reassignment of another team's work.
3. Opened the Team 1 Guacamole desktop at `:8082`. Opened Wireshark, loaded
   `/evidence/network/sensor.pcap`, and applied `udp.port == 514`. The visible
   packet details exposed the request identifiers and transfer destination.
4. Opened Wazuh at `:8443` and used Discover with the `silent-ridge-*` index.
   The default short time range had no useful results; changing to the visible
   seven-day range produced 498 hits. Entering the coached query
   `data.host:WS-31` produced a visible 262-hit state, but the table did not
   narrow cleanly to only WS-31 records and Wazuh displayed a DQL/Lucene warning
   plus repeated 403 UI-setting notices. This is recorded as a defect rather
   than treated as proof of a finding.
5. Opened CTFd from the public `:8083` hostname and authenticated as the Team 1
   participant. The `/silent-ridge` route rendered `500 — An Internal Server
   Error has occurred`; a stale alternate tab also showed `403 Forbidden` for
   that route. Screenshot: `13-ctfd-silent-ridge-500-blocker.png`.
6. Because no CTFd answer form was available, no answer was submitted and no
   screenshot claiming a `Correct` result was fabricated.

## T01 — Wireshark / `network/sensor.pcap`

Human route: Guacamole desktop → Wireshark → File/Open →
`/evidence/network/sensor.pcap` → display filter `udp.port == 514`.

The capture is replayed/reconstructed evidence. Transmission metadata supports
the recorded exchange but does not establish human receipt, reading, or intent.

| Question | Expected answer | Explanation and evidence |
|---|---|---|
| T01-Q1 | `WS-17` | The filtered sensor record identifies WS-17 as the source host associated with the document traffic. The Wireshark route and filter are visible in the desktop evidence; see `04-wireshark-t01-req72-destination.png`. Not submitted because CTFd was unavailable. |
| T01-Q2 | `req-71` | The filtered request record carries request identifier `req-71`; this joins the document request to the same reconstructed exchange. Not submitted because CTFd was unavailable. |
| T01-Q3 | `req-72` | The adjacent filtered transfer record carries `req-72`; the visible packet details in `04-wireshark-t01-req72-destination.png` show this identifier. Not submitted because CTFd was unavailable. |
| T01-Q4 | `198.51.100.77` | The transfer record's destination field is the documented training address `198.51.100.77`. This is a destination observation only, not proof of human receipt or intent. Not submitted because CTFd was unavailable. |

## T11 — Wazuh / `wazuh/telemetry.jsonl`

Human route: Wazuh → Explore → Discover → index `silent-ridge-*` → seven-day
time range → coached query `data.host:WS-31`.

The expected values are preserved from the acceptance matrix, but T11 was not
claimable and the live query did not produce a clean WS-31-only result in the
visible table. The expected limitation is important: historical replay is not
a live observation, and missing telemetry is not proof that an event did not
occur.

| Question | Expected answer | Explanation and evidence |
|---|---|---|
| T11-Q1 | `BriefSync` | The acceptance matrix identifies the application in the WS-31 process record as BriefSync. The query attempt is captured in `06-wazuh-ws31-query-262-hits.png`; no CTFd submission was possible. |
| T11-Q2 | `08:45:00` | The documented WS-31 process-start time is 08:45:00. This is a historical telemetry timestamp, not a live process observation. No CTFd submission was possible. |
| T11-Q3 | `08:50:00` | The documented WS-31 process-stop time is 08:50:00. No CTFd submission was possible. |
| T11-Q4 | `no` | The documented WS-31 record does not show a corresponding external transfer. This bounded absence must not be generalized beyond the supplied historical record. No CTFd submission was possible. |

## Exact blockers and limitations

- CTFd `/silent-ridge` returned a visible 500 after authentication, preventing
  all eight answer submissions and all post-submit `Correct` screenshots.
- T11 remained dependency-locked because T10 was still available in the IRIS
  queue. I waited/reloaded and did not claim T10 or any other team's ticket.
- Wazuh displayed usable historical data in the seven-day range, but the
  coached `data.host:WS-31` query produced a mixed visible result set and
  parser/permission notices. The T11 expected values are therefore documented
  as matrix-derived, not live-verified in this run.
- IRIS contains participant-facing links whose visible values point to the raw
  `192.168.1.200` host even though the rehearsal was run on the fixed public
  tailnet hostname. This is a deployment defect and is detailed in
  `defects.md`.
