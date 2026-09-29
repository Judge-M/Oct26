# Facilitator capture point — T01 network map

Facilitator-only. Do not paste this file, the screenshot it describes, or the
authoring record labels into participant text. The map itself is participant
facing and is unlocked by the platform; this note is the rehearsal evidence for
the completed T01 task.

## What the map is

`assets/t01-network-map-v1.json` is the only source of the map data.
`ridge/network_map.py` renders it into a single self-contained offline HTML
document: inline CSS, inline script, no fonts, no images, no external
reference of any kind. It is an additional analytical view of evidence T01 has
already exposed. It replaces no T01 question, adds none, and scores nothing.

It is **not** a released evidence file. `ridge.transport` publishes a ticket's
release files when the ticket unlocks, and T01 unlocks at run start, so a
released map would name `198.51.100.77` before T01-Q4 was answered. Instead:

- `ridge.web.network_map_link` adds the link to the CTFd question page once the
  snapshot reports T01 `complete`.
- `ridge.service` answers the `network_map` action with HTTP 403 until
  `State.ticket_complete('T01')` is true, so the page cannot link to a view the
  controller would refuse.
- `integrations/ctfd_silent_ridge` serves the rendered document at
  `/silent-ridge/network-map`, authenticated, after that gate.

## Rehearsal steps

1. Start the run and let a team claim T01. Confirm the CTFd question page shows
   **no** network-map link. That absence is the control; screenshot it if the
   rehearsal is checking the gate.
2. Answer all four T01 questions. The link appears at the foot of the question
   page in the T01 completion state. Reload once if the page was already open.
3. Open the map from that link, or render the identical file for the desktop:

   ```
   python -m ridge.network_map work/t01-network-map.html
   ```

   Then open `file:///…/work/t01-network-map.html` in the team desktop's
   Firefox 140 ESR. The two routes serve byte-identical documents; the offline
   file is the one that proves the map needs nothing from a network.
4. Select the upload edge (`req-72`, `09:06:00Z`). Confirm the panel names the
   supporting records and that the network/proxy.csv, network/sensor.pcap and
   hunting/siem.jsonl sources light up in the graph.
5. Select the dashed acknowledgement edge. Confirm the panel states that the
   acknowledgement carries its own request identifier, that no record says which
   request it answers, and that it does not show a person reading anything.

## Screenshot moment

Capture the desktop at step 4, with the selected `req-72` edge and its record
panel both visible in one frame. That single frame evidences all of the
acceptance points at once: the legend, the directed edges with request
identifiers and UTC times, the observed/inferred distinction, the supporting
record and its `/evidence/…` source path, and the boundary statement.

Take a second frame at step 5 if the rehearsal needs the inferred edge on the
record. Do not crop the boundary panel out of the first frame — a map
screenshot without it is not acceptable evidence for this issue.

## Checks to run before the rehearsal

```
python -m unittest tests.test_network_map -v
python -m ridge.network_map work/t01-network-map.html
```

The second command refuses to write a document that could reference an external
resource. Treat a refusal as a defect, not as a warning.

## Coaching notes

Teams tend to read the map as a conclusion. Two questions close that gap, and
both are already answered in the panel text:

- Which single record states that a person received the uploaded body? None does.
- The dashed edges are this map's reading of two records. Which two, and is the
  join recorded anywhere?

Issues 59 and 66 asked for a "shadow network" tone. Canon has no such name and
T20-Q4 scores `no` for adversary intent, so the map carries no codename and
names no group, operator or sponsor. Do not supply one while presenting it.
