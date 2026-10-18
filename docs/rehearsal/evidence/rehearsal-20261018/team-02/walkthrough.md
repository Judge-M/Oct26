# Operation Silent Ridge — Team 2 rehearsal walkthrough

Date: 2026-10-18  
Event: `ridge-oct26-fresh`  
Role: Team 2  
Scope: T02 and T12  
Browser: isolated Codex in-app browser  
Participant hostname: `https://desktop-t5pf26o.tail799fee.ts.net`

## Outcome

T02 was already claimed by Team 2 and remains held. The coached evidence route was inspected in the Team 2 Guacamole desktop: Evidence → `network` → `dns.pcap` → Wireshark. The capture displayed four DNS packets, including the query from `10.26.10.17` to the DNS server and the corresponding response path.

No CTFd question reached a verified `Correct` result. The CTFd event route returned a visible HTTP 500 page and later hung during a retry. Because IRIS requires the held ticket to be completed before another ticket can be claimed, T12 was not claimed and no other team ticket was touched.

## IRIS navigation and queue evidence

1. Opened the trusted IRIS surface at `:8081` in the isolated browser.
2. Signed in as the Team 2 participant account. The event queue visibly reported `Team: team-02`, `Exercise: running`, `You hold: T02`, and `0 updates awaiting synchronization`.
3. The T02 card visibly reported `Wireshark · active · Owner: team-02` and offered “Start this ticket's questions.”
4. T12 visibly remained `Wazuh · available · Owner: available` with a Claim ticket control.
5. T12 was intentionally left unclaimed because T02 was still held and incomplete.

The IRIS page also exposes internal raw-IP links for the question and shared-task routes even when reached through the trusted hostname. This is recorded as a defect; the rehearsal stayed on the trusted hostname and did not follow those raw-IP links.

Queue/claim screenshot capture: `screenshots/01-iris-team2-t02-held-t12-available.png` (captured in the isolated browser session; see the screenshot index for persistence status).

## T02 — Resolve names and compare conversations

Tool and evidence path from the acceptance matrix: Wireshark, `/evidence/network/dns.pcap`. The coached route was opened manually in the Team 2 desktop by opening the Evidence shortcut, navigating to `/evidence/network/`, and opening `dns.pcap` in Wireshark. The visible packet list contained four DNS packets; packet 1 showed source `10.26.10.17` and destination `10.26.20.53`.

The question answers below are the matrix answers and were not submitted because CTFd did not provide a functioning question page.

### T02-Q1

Question: Which name resolved to the external destination?  
Answer: `relay.archive.example`  
Justification: The matrix identifies the DNS selection as `dns` and the expected resolved name as `relay.archive.example`; Wireshark visibly showed the DNS query/response conversation in `dns.pcap`.  
Evidence source: `/evidence/network/dns.pcap`  
Limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.

Screenshot capture: `screenshots/02-t02-dns-pcap-open.png`.

### T02-Q2

Question: What address did it resolve to?  
Answer: `198.51.100.77`  
Justification: This is the acceptance-matrix answer for the DNS response in the opened pcap. It was not submitted or verified because CTFd remained unavailable.  
Evidence source: `/evidence/network/dns.pcap`  
Limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.

Screenshot capture: `screenshots/03-t02-dns-pcap-response-route.png`.

### T02-Q3

Question: Which client made that lookup?  
Answer: `10.26.10.17`  
Justification: The selected first packet visibly showed source `10.26.10.17`; the acceptance matrix identifies that host as the client.  
Evidence source: `/evidence/network/dns.pcap`  
Limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.

Screenshot capture: `screenshots/04-t02-dns-pcap-client-10-26-10-17.png`.

### T02-Q4

Question: What TTL was returned, in seconds?  
Answer: `60`  
Justification: This is the acceptance-matrix answer for the DNS record. The answer was not entered because the CTFd event page failed before the question form was available.  
Evidence source: `/evidence/network/dns.pcap`  
Limitation: Replayed or reconstructed evidence; transmission metadata does not establish human receipt, reading, or intent.

Screenshot capture: `screenshots/05-t02-dns-pcap-ttl.png`.

## T12 — Map collection coverage

Tool and evidence path from the acceptance matrix: Wazuh, `/evidence/wazuh/telemetry.jsonl`. T12 was not claimable for this rehearsal because IRIS kept T02 held and CTFd could not complete T02. The Wazuh surface was nevertheless opened directly and the Team 2 desktop shortcut was inspected. The direct Wazuh surface remained at its login screen with a visible invalid-credentials error, so no telemetry record was accessed.

The matrix answers are recorded for completeness only; none were submitted or verified as Correct.

### T12-Q1

Question: Which workstation has no network collection?  
Answer: `WS-31`  
Justification: Acceptance matrix answer for the coverage record.  
Evidence source: `/evidence/wazuh/telemetry.jsonl`  
Limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.

Screenshot capture: `screenshots/06-t12-wazuh-login-blocker.png` for the Wazuh login blocker; no T12 question screenshot was reachable.

### T12-Q2

Question: When does the DOCS-1 collection gap start?  
Answer: `09:14:00`  
Justification: Acceptance matrix answer; not submitted because T12 could not be claimed and Wazuh telemetry was inaccessible.  
Evidence source: `/evidence/wazuh/telemetry.jsonl`  
Limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.

No per-question screenshot: T12 was not claimed and the question page was unavailable.

### T12-Q3

Question: When does that gap end?  
Answer: `09:18:00`  
Justification: Acceptance matrix answer; not submitted because T12 could not be claimed and Wazuh telemetry was inaccessible.  
Evidence source: `/evidence/wazuh/telemetry.jsonl`  
Limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.

No per-question screenshot: T12 was not claimed and the question page was unavailable.

### T12-Q4

Question: How many seconds fast is the WS-17 device clock?  
Answer: `120`  
Justification: Acceptance matrix answer. The walkthrough limitation is to report the offset without applying it a second time. No submission was possible in this run.  
Evidence source: `/evidence/wazuh/telemetry.jsonl`  
Limitation: Historical replay is not a live observation. Missing telemetry is not proof that an event did not occur.

No per-question screenshot: T12 was not claimed and the question page was unavailable.

## CTFd question flow

The trusted CTFd login surface accepted the Team 2 participant session, but `https://desktop-t5pf26o.tail799fee.ts.net:8083/silent-ridge` visibly returned `500 — An Internal Server Error`. A fresh retry on the same trusted hostname did not produce a question page and later timed out while the browser was waiting for the route. Consequently, there are no successful answer screenshots and no visible Correct results to report.

Error screenshot capture: `screenshots/10-ctfd-event-500.png`.

## Human navigation notes

- All browser work used the isolated Codex in-app browser, never the user's logged-in Chrome.
- All live surfaces used the trusted Tailscale hostname.
- The Team 2 Guacamole session was corrected from a stale desktop session to `desktop-02` before evidence inspection.
- The Wireshark file-open dialog initially reported a file-not-found error after a malformed entry; the file was then opened successfully through the Evidence file manager.
- The Wireshark display filter field was left unchanged after the remote desktop input path accepted only a partial character; the visible packet list itself was sufficient to confirm the coached pcap route.
- No password changes, deletion, uploads, event configuration changes, commits, or pushes were performed.

