# N2 Receipt — One Real Desktop Through Guacamole, Two Teams (2026-09-18)

Scope per NEXT.md N2: container desktop through Guacamole with the seeded
prepared case, two teams, repeatability, isolation, 3 concurrent clients, WS17
case + BriefSync search, PCAP, Cutter, and controller evidence publication
observed on desktops including after reconnect. No ten-team capacity claim.

All secrets stayed in the gitignored runtime directory; none appear here.

## Stack brought up

- `guacamole/guacd:1.5.5`, `guacamole/guacamole:1.5.5`, `postgres:16.8-alpine`
  pulled by tag; digests recorded locally at pull time.
- Official schema generated from the image itself
  (`initdb.sh --postgresql`, 23 tables) and mounted as
  `/docker-entrypoint-initdb.d/001-initdb.sql`; provisioning SQL from
  `deployment/expanded/guacamole.py` mounted as `002-provision.sql`.
- External network `silent-ridge-n1-desktop` carries guacd ↔ desktop VNC only;
  no VNC port is published to the host. Guacamole UI bound to 127.0.0.1:8082.
- Two desktops (`desktop-team01`, `desktop-team02`) from the rebuilt
  `silent-ridge-desktop:dev`, each with the hash-verified prepared case mounted
  read-only and seeded into `~/Cases/WS17` by the entrypoint.

## Provisioning verification (against the real PostgreSQL)

- 2 connections (`desktop-01`, `desktop-02`; vnc, max_connections=4),
  3 user entities, 10 connection parameters, 2 connection permissions.
- `guacadmin` disabled; `guacadmin/guacadmin` login rejected (HTTP 403).
- Re-applying `002-provision.sql` changed zero row counts — idempotent.

## Isolation and concurrency (live, scripted Guacamole protocol client)

- team01 login sees only `desktop-01`; team02 sees only `desktop-02`.
- team01 opening a tunnel to desktop-02's identifier: connection refused by the
  server (websocket close, error 516).
- 3 concurrent sessions on `desktop-01` as team01: all live. A 4th was allowed
  (max_connections=4); a 5th was refused (error 797).
- While 4 sessions were held, the desktop-team01 container showed exactly 4
  established TCP connections on VNC port 5901; desktop-team02 showed 0.
  (First count read 0 due to a wrong hex port in the check itself — 5901 is
  0x170D; corrected and re-measured.)

## Case content on the desktop

- Autopsy case `~/Cases/WS17/WS17.aut`: `autopsy.db` SQLite integrity ok,
  53 `tsk_files`.
- Keyword index queried with the image's own bundled Solr 8 against the case
  core (`ws17_20260916_021315_20260916_021315`, schema 2.3): 90 indexed
  documents, `text:BriefSync` → **6 hits** — matches the authored expectation
  (`assets/desktop-v1.json`). Note: the core's `dataDir` is flat `data/`; the
  case stores the index at `data/solr8_schema2.3/`, so a standalone Solr must
  map that subdirectory as the core data dir.
- `network/sensor.pcap` visible at `/evidence/network/sensor.pcap` on both
  desktops; capinfos: 24 packets (matches facilitator solutions); `dns.pcap`:
  4 packets. Wireshark itself is GUI; capinfos is the scripted proof.
- Cutter 2.5.0 (rizin 0.9.1) analyzed `/originals/originals/windows/
  brief-viewer.exe`: PE, 32-bit, 3 functions after full analysis. GUI
  walkthrough remains a human check.

## Evidence release (real controller path)

- Release bundle built with `python -m expanded.prepare` (initial evidence +
  vault tickets T07/T09/T11/T19).
- Desktops and the publish call share one host directory: desktops mount it as
  `/evidence` (ro); `ridge.evidence_release.publish` ran in the integration
  image with `RIDGE_EVIDENCE_PUBLIC` on the same directory.
- Published T19 (`network/dlp-body.txt`, `network/dlp-metadata.json`) and T07
  (`identity/late-auth.csv`, which also bulk-indexed its telemetry row:
  index `silent-ridge-oct26` went 505 → 506 documents).
- Files visible on both desktops immediately; re-publishing T19 was a no-op
  (idempotent).

## Bug found by the restart test, and fix

`docker restart` of a desktop crash-looped: the writable layer keeps
`/tmp/.X1-lock` and `/tmp/.X11-unix/X1`, so Xtigervnc refused display :1
("Server is already active for display 1"). Fixed in
`deployment/expanded/desktop/entrypoint.sh` (remove stale locks before
starting Xtigervnc), image rebuilt, desktops recreated.

After the fix: restart → healthy → `/evidence` releases and the seeded WS17
case still present → fresh Guacamole sessions to both desktops live.

## Smoke test repairs (`tests/desktop_container_smoke.sh`)

Two host-portability fixes, both verified by full green runs on this Windows +
Docker Desktop host (script exit 0):

1. The post-restart marker check used a bare `docker exec <c> test -f /home/...`
   argument, which MSYS/Git Bash rewrites to a Windows path — the check could
   never pass on Windows even though the marker persisted. Now `bash -c`.
2. The fixed `sleep 5` raced container start on a loaded host; replaced with a
   bounded poll that fails fast with logs if the container actually stopped.

Root-causing note for the record: several "marker missing" readings during
debugging were the MSYS rewrite, not data loss — direct `bash -c` checks and
unique-content markers proved the writable layer persists across restart.

## Gates

- `python -m ridge.deploy build` × 4 (iris, ctfd, integration, desktop) after
  the entrypoint change; `verify-build` passes with image IDs and the shared
  source fingerprint recorded in the local receipts file.
- `python -m unittest discover -s tests`: **221 tests, OK**.

## Not claimed / remaining

- No ten-team capacity claim; two desktops ran. Host headroom on the build
  machine was comfortable, but the event host must be measured separately.
- GUI walkthroughs (Autopsy open case, Wireshark filter, Cutter window, Xfce
  usability through Guacamole rendering) are verified at protocol level only;
  one human pass through the Guacamole UI is still owed before the event.
- Guacamole team credentials live only in the runtime directory; distribution
  to participants is an organizer step.
