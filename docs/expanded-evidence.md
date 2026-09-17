# Evidence preparation and release gates

The canonical incident remains the one described in the historical ground truth:
WS-17 viewer activity; S-41 reuse; reset versus revocation; v3 versus v4;
transmission versus human reading; denied roster access; clock offsets; DOCS-1
gaps; unresolved WS-31; benign WS-22. No other storyline is introduced.

## Generated and checked here

`expanded/prepare.py` creates an 8 MiB FAT16 image with a recoverable deleted
movement-cache entry, visible plan-v3 and browser-history text; a valid DNS PCAP;
reconstructed syslog PCAP matching the proxy CSV; browser, authentication, server
and coverage exports; and historical JSONL containing interleaved ordinary events.
Stable source hashes replace conspicuous special suspicious-record ID ranges in
the principal initial CSV and SIEM sources. Request IDs still support correlation.
The expanded PCAP is rebuilt from the remapped CSV, not left with stale IDs.

The disk is a purpose-built native FAT filesystem, not an image of an acquired
Windows installation. Network captures are synthetic reconstructions, not original
TLS capture. SIEM records are historical replay. Device timestamps remain labeled;
WS-17 times are normalized once for the SIEM. These distinctions are participant
visible and must survive packaging.

Only `initial/` is initially published. `controller/releases/Txx/` holds authored
follow-up evidence. The integration publishes those files when the corresponding
ticket unlocks and indexes released CSV records with stable document IDs.
Repeated publication accepts identical files and rejects conflicting content.
The controller preparation fixtures and source manifests are not desktop shares.

## Native Windows and memory sources

The JSON under `controller/preparation-fixtures/` is explicitly synthetic. It is
not EVTX-derived evidence and is not a native memory capture. Do not relabel it or
use it to certify these requirements. A separate Windows Sandbox reconstruction
has now supplied native EVTX and memory. Its measured PIDs, task registration,
memory process records and live connection snapshot drive T13–T16. See
[the acquisition record](native-windows.md). Actual acquisition timestamps are
preserved; the historical incident facts and clock offsets are unchanged.
Any acquisition or expensive processing happens before the event on a separate
preparation system. No participant imaging or ingestion wait is permitted.

Each prepared result must include source ID, original SHA-256, original path,
EVTX record ID or memory offset, parser/tool version, exact command/configuration,
time semantics, and neutral observations. Retain all originals in the versioned
artifact store. Do not put solutions into investigator bookmarks or annotations.
The process/connection values in the question outlines must be reconciled with
the final captures, rather than presenting unmeasured fixture offsets as facts.

## Autopsy case preparation

Use the exact pinned Linux template early, before building the full data set.
Create a small representative case with the FAT16 image, one parsed native log
record and one prepared memory finding. Confirm filesystem browsing, deleted-file
recovery, keyword search, metadata inspection, and traceability back to originals.
The module/API model is documented in [Autopsy 4.22 ingest development](https://www.sleuthkit.org/autopsy/docs/api-docs/4.22.0/mod_ingest_page.html).

A custom ingest module has not been implemented. The intended initial import is
logical files containing neutral, source-referenced prepared results, searchable
in Autopsy's file/text/keyword views. Confirm this provides adequate navigation
and filtering with beginners. If it does not, implement an ingest module before
acceptance; do not substitute a participant-facing analysis platform.

Finish expensive ingest/indexing in preparation. Close Autopsy before packaging.
Copy the closed case per team into a writable local directory. Original evidence
paths must resolve to the shared read-only mount on every clone. Verify all source
hashes, then reopen each copy without re-ingest or database repair. There are no
additional ingest steps required for the published version-two prepared case.
The case was reopened in the desktop GUI; its 90-document keyword index returned
six matches for `BriefSync`. The source archives and validation inventory are
listed in `assets/autopsy-case-v2.json`.

### Case path contract

An Autopsy question separates its evidence reference from the tool entrypoint:

- `evidence` is a released source under `/evidence` (for example
  `disk/WS17-fat16.img` or `prepared/windows-process.json`). Controller preflight
  (`ridge.preflight.check`) verifies it against the published release.
- `case_entrypoint` is `~/Cases/WS17/WS17.aut`, the writable case copy on each team
  desktop; the read-only template is `/opt/silent-ridge/prepared-case/WS17`.
  Desktop readiness (`ridge.preflight.check_desktop`) verifies that entrypoint.
- Originals stay under `/originals`; neither `/evidence` nor `/originals` is writable.

The old `/evidence/autopsy/WS17/WS17.aut` path never existed on the evidence mount
and is no longer emitted. Tickets generated before this contract must be regenerated
with `python expanded/author.py`. `ridge.preflight.check` rejects any `.aut` or
`autopsy/` evidence path explicitly instead of reporting it as a missing source, and
it does not require a writable case on the controller.

## Harmless Cutter exercise

Build `expanded/binary/brief-viewer-training.c` on the pinned Linux preparation
host with debug symbols and optimization disabled, for example:

```text
cc -O0 -g -fno-inline -o brief-viewer-training expanded/binary/brief-viewer-training.c
```

Record compiler/version/command and the binary hash. This program prints training
text and has no networking, persistence, credential or file-acquisition behavior.
It is a transparent surrogate for learning strings/configuration and one branch.
Verify the outlined function/strings workflow in Cutter before release. No
participant-time compilation is required. The compiled binary is published with
compiler/source hashes in `assets/training-binary.json`; Cutter 2.5.0 successfully
analyzed it in the Ubuntu desktop guest (11 functions and 16 strings).

## Workload

20 tickets × 65 estimated team-minutes = 1,300 estimated team-minutes, or 260
minutes with five teams. This excludes orientation, breaks and AAR. It is not a
measurement and does not demonstrate four hours of meaningful analysis. Several
follow-ups depend on earlier discoveries, so the quotient alone does not prove
parallel utilization. Rehearse with representative beginners; record per-ticket
time, hint use, dead ends, idle time, and dependency stalls. Expand or revise the
evidence/questions if actual active time falls below 240 minutes per team.
