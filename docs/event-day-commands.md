# Event-day command sheet

One page, cold machine → running event → teardown. Tested end-to-end on the
dev host (dress rehearsal, 2026-09-23). Replace `<LAN-IP>` with the event
machine's LAN address and `R` with your chosen runtime directory (private —
it holds secrets and state; never commit it).

Timings are honest: first `up` takes 10–20 minutes including image loads and
the guacd 5-minute healthcheck. Re-run any `up` that reports "services not
ready" — it is an idempotent reconcile, not a failure.

## 0. One-time host prep (before event week)

- Docker Desktop / Docker Engine running, Python 3.11+, Git + Git LFS
- 32 GB RAM / 16 cores minimum for 10 teams (validated by the capacity
  model with 20% memory headroom; 64 GB is comfortable)
- **Install from the offline release bundle** (the supported cold path):
  download every asset of the latest release, assemble the bundle directory
  exactly as its release notes show, then from a repo checkout run
  `python -m ridge.offline_install <bundle-dir> <install-dir>` — it
  hash-verifies everything, loads all images, and writes a receipt.
- Then extract the content assets (once, next to the install):

  ```bash
  mkdir assets && cd assets
  tar -xzf <bundle-dir>/evidence/evidence-public.tar.gz
  tar -xzf <bundle-dir>/dependencies/case-and-wazuh-config.tar.gz
  tar -xzf <bundle-dir>/dependencies/release-vault.tar.gz
  mkdir originals && tar -xzf <bundle-dir>/memory/WS17-native-v1.tar.gz -C originals
  cd ..
  ```

  This gives you `assets/evidence-public`, `assets/case-template`,
  `assets/wazuh-config`, `assets/release-vault` and `assets/originals` —
  the five directories `local.json` points at in step 2. (Windows 10+
  ships `tar.exe`; any extractor works.)
  Note: `v0.9.0-drill` predates `release-vault.tar.gz`; on that release copy
  `work/release/controller/releases` from a build host into
  `assets/release-vault`, or the first follow-up ticket fails mid-event.
- Participant laptops on the same LAN; no internet required after this point

(Building images from source instead — `python -m ridge.deploy build
--component all && python -m ridge.deploy verify-build` — only makes the
container images, not the content assets; the full content pipeline is a
developer path documented in `docs/handoff/BUILD-FIRST.md`. Event hosts
should use the bundle.)

## 1. Profile (once per host)

Copy `deployment/profiles/example-two-team.json` to `event-profile.json` and edit
**only**:

- `event.event_start` / `duration_minutes`
- `addresses`: set `central_bind_ip` to `<LAN-IP>` and the three
  `*_public_url` values to `http://<LAN-IP>:8081`, `:8083`, `:8082`

Do **not** edit the roster — team count is a start-time switch (`--teams`).

## 2. Runtime local.json (once per host)

Create `R/local.json` pointing at the asset directories extracted in step 0:

```json
{
  "assets": {
    "evidence_public": "<abs path>/assets/evidence-public",
    "release_vault": "<abs path>/assets/release-vault",
    "case_template": "<abs path>/assets/case-template",
    "originals": "<abs path>/assets/originals",
    "wazuh_config": "<abs path>/assets/wazuh-config"
  },
  "ports": {"iris": 8081, "ctfd": 8083, "guac": 8082,
            "wazuh_dashboard": 8443, "wazuh_indexer": 9200},
  "index_name": "silent-ridge-oct26"
}
```

Keep the `wazuh_config` directory and the runtime secrets from the same
generation (it embeds the hashed admin password; a mismatch fails with
HTTP 401 from the indexer job).

## 3. Bring the event up (T-minus ~30 min)

```bash
python -m ridge.deploy doctor
python -m ridge.deploy up --teams 10 --profile event-profile.json --runtime R
# re-run `up` until every stage verifies (guacd needs ~5 min for its first healthcheck)
python -m ridge.deploy status --profile event-profile.json --runtime R   # expect event_ready: true
```

`up` stops at a verified, **paused** state — participants see nothing yet.
Hand out team accounts from `R/secrets/team-credentials.json` and the shared
Wazuh reader login from `R/secrets/wazuh_reader`.

## 4. Start the event

```bash
python -m ridge.deploy start --profile event-profile.json --runtime R
```

Participant URLs (all in their own laptop browser):
`http://<LAN-IP>:8082` desktops · `:8081` IRIS · `:8083` CTFd ·
`https://<LAN-IP>:8443` Wazuh.

Opening briefing: project **`docs/event-day-deck/event-day-deck.pdf`**
(13 slides, story + click-by-click setup — plays anywhere, no software
needed). The editable source is `event-day-deck.pptd` in the same folder.
The `<event-address>` shown in the deck is the `<LAN-IP>` above.

## 5. During the event

```bash
python -m ridge.deploy status --profile event-profile.json --runtime R
python -m ridge.cli announce --operator EXCON --text "..."          # message all teams
python -m ridge.deploy pause --profile event-profile.json --runtime R   # freeze the clock
python -m ridge.cli recover T03 --generation 1 --operator EXCON --reason "..."
```

Symptom → action table: `docs/runbook.md`.

## 6. Capacity rehearsal (F03, before or during a quiet window)

```bash
PYTHONPATH=. python -m expanded.load --config f03-config.json --duration 1800 --output work/f03/event-run
```

Config template and acceptance checks: `docs/f03-rehearsal.md`. The run
self-labels CERTIFYING only at 10 teams on a ≥32 GiB host. Manual desktop
usability pass in parallel (open 2–3 desktops, launch Autopsy, search).

## 7. Teardown

```bash
python -m ridge.deploy backup --profile event-profile.json --runtime R   # verified recovery set
python -m ridge.deploy down   --profile event-profile.json --runtime R   # stops; keeps all data
# only when the export is safely archived:
python -m ridge.deploy down --volumes --profile event-profile.json --runtime R
```

## Traps (all hit at least once in rehearsal)

- Re-run `up`; it reconciles, never resets.
- Never open `R/state/state.sqlite` from host tools while the stack runs
  (SQLite locks don't cross Docker Desktop bind mounts → integration 503s).
- Roster changes after `up` are refused by design; a different team count
  means a fresh runtime directory.
- `down` keeps data; only `--volumes` wipes, and it demands a verified
  backup first.
