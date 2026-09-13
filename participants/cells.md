# Five cooperative investigation assignments

All five tickets concern the same incident. Every cell can read and comment on all
tickets. The owning cell maintains its status and final assessment. Each cell should
assign an analyst, evidence recorder and reporter; combine roles for smaller teams.

| Ticket | Cell and initial sources | Required independent product | Useful correlation |
|---|---|---|---|
| 1 | Network: proxy.csv, dns.csv, sensor.pcap | Timeline of download and egress, byte counts, confidence and visibility limits | Compare request IDs to server; file identity to DLP when released |
| 2 | Endpoint: events.csv, clock.txt, browser.sqlite | Normalized process/file/network timeline, persistence assessment, preservation request | Compare corrected times and file hash with network and server |
| 3 | Identity: auth.csv, policy.txt | Session and account timeline; assess password-reset effectiveness | Compare S-41 to document access and process activity |
| 4 | Server and data: access.csv, catalog.csv, collection.txt | Bound successful versus denied access, object versions and collection gaps | Compare req-71 and file hash; request current-version clarification |
| 5 | Hunting: siem.jsonl, coverage.csv | Hypothesis-driven cross-enterprise hunt, scope and coverage matrix | Solicit corroboration from all cells; distinguish similar artifact names |

Network: filter high-volume baseline traffic, examine the PCAP in Wireshark or
tshark, and explain what a successful POST does and does not establish. The capture
is reconstructed sensor telemetry, not an original TLS session.

Endpoint: use a SQLite browser or `sqlite3 browser.sqlite` and inspect `.schema`
before querying downloads. Separate normalized browser timestamps from device times.
Identify process ancestry, file creation and scheduled tasks; avoid executing anything.

Identity: group rows by session, then compare source address, login type and MFA
semantics. Explain alternate explanations and the distinction between a password
reset and session invalidation using the supplied policy.

Server: enumerate successful reads and denied requests separately, join the catalog,
and state precisely which claim is supported by server-side bytes alone. Account for
the collector gap and the unavailable current-plan content.

Hunting: write two hypotheses and a query or reproducible filtering method for each.
Track supporting and contradicting observations, affected hosts, hosts needing
collection, and hosts for which no conclusion is possible. Ask other cells for row IDs.

Every cell: post an initial update by minute {{initial_report}}, respond to command deadlines,
comment on at least one other cell's ticket with useful evidence, and nominate
one next collection step that could change your assessment.


## Joint assessment ownership

The hunting cell reporter coordinates the joint assessment. Every cell posts a
contribution on ticket 5 by elapsed minute {{cell_handover}}, linking its own ticket
and comment IDs, facts, confidence, unresolved questions and defensive priorities.
The hunting reporter reconciles disagreements and posts a comment headed
JOINT ASSESSMENT on ticket 5 by minute {{joint_report}}. Keep unresolved differences
explicit; agreement is not a prerequisite for reporting. Command acknowledgments
are in the read-only controller ledger, not comments attributed to a cell.
In Jira use the hunting issue as ticket 5 and link the same five contributions.
