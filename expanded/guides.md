# Getting started with the investigation

Open **Incident queue** and claim an available ticket. Open **Questions and help**
to see that ticket's questions. Your team can work on one ticket at a time. Every
correct answer earns one point and automatically records a finding. There is no
report to write. Use any help level, including the final walkthrough, without a
point penalty. If you relinquish a ticket, its completed answers are preserved.

## Evidence and working files

Open **Evidence** to browse the released read-only files. Save working notes and
exports in **Workspace**. Use **Scratch** for temporary files. Open your team's
copy of the prepared case in **Cases**. Do not attempt imaging, live containment,
agent installation or a large ingest job during the exercise.

All material is fictional. A historical replay is not a current observation.
Read each source's collection period and time convention. Correct device times
only when the source explicitly gives an offset; do not adjust normalized times
again. A missing record can reflect a collection gap.

## Wireshark

Use File > Open to select a PCAP. Enter a display filter in the bar above the
packet list and press Enter. A red filter bar means the syntax needs correction;
clear the bar to restore all packets. Select a packet and expand the protocol
fields below it. View > Time Display Format controls displayed time conventions.

Worked example: in the reconstructed sensor capture, `udp.port == 514` selects
syslog messages. The outer packet addresses identify collectors. Expand the
syslog message to inspect the embedded proxy record and its own source/destination.
The same packet can therefore contain two different pairs of addresses without
being contradictory. Use Statistics > Conversations to compare the outer capture
conversations, then return to the embedded incident records.

## Autopsy

Use Open Existing Case to open the writable case copy in Cases. Expand Data
Sources, select a file and use the Text, Hex and metadata views. Keyword Search
finds indexed text; clear an old search when switching topics. Deleted Files is
useful for items absent from the ordinary directory listing. A deleted FAT short
name may have an unknown first character, so search by its surviving suffix.

Worked example: select README.TXT in the training disk and inspect its text and
size. This is a known ordinary file for practicing navigation. For prepared log
or memory findings, inspect the source reference as well as the displayed value.
Use that reference to find the original artifact. Do not add solution bookmarks
to the shared template.

## Wazuh

Open the Wazuh dashboard in your own laptop browser (the `:8443` address and
shared reader login come from your facilitator) — not inside the shared
desktop. Open Discover, select the exercise's historical data view, and set
the absolute scenario-date UTC range shown in the question. Expand individual
rows to inspect
field names. Start broad, then add one filter at a time.

Worked example: search `data.host:WS-22`. Examine ordinary activity and its source
field before narrowing to a task or document event. If a query returns nothing,
clear the query and confirm the date range and selected data view. A host name in
one source may be an IP address in another; compare the provided inventory.

## Cutter

Open the harmless training binary and allow ordinary static analysis. Do not start
debugging or execute the sample. Open the Strings view and select a string to find
its references. Open a named function and compare graph/disassembly views.

Worked example: find the introductory training message and locate the function
that prints it. The existence of a string is a clue about the file; it is not
proof that an incident system used that value or executed the related function.

## Finishing a ticket

Answer only the requested value in the stated format. Case and outer whitespace
are ignored. If the answer is not accepted, inspect the next free help level.
Accepted work is retained even when a connection fails; return to the queue and
history to check progress. When the last question is answered, the ticket closes
for all teams. Choose another available ticket and use the findings already shared.
