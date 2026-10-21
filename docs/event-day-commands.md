# Operator installation and recovery command sheet

This is the command reference for one-time installation, operator recovery and
post-event teardown. It is **not** the normal facilitator path. After the two
boot tasks have passed their worker-first reboot test, event day requires no
server commands: power on the worker, power on the primary, wait for the
registration page, present the opening deck, and tell teams to begin. The
primary boot task performs `up` and `start`.

For preparation and recovery, replace `<LAN-IP>` with the primary's LAN address
and `R` with the private runtime directory. It holds secrets and state; never
commit it.

Timings are honest: first `up` takes 10–20 minutes including image loads.
Guacd now probes every 10 seconds. Re-run any `up` that reports "services not
ready" — it is an idempotent reconcile, not a failure.

## 0. One-time host prep (before event week)

**On a fresh machine, use the fully spelled-out copy-paste version of this
section: `docs/event-machine-cold-start.md`, using the release that contains
this profile and its 33-slot Compose pool.** The summary below is the reference.

- Docker Desktop / Docker Engine running, Python 3.11+, Git + Git LFS
- Capacity is profile- and hardware-bounded. The current 33-slot / eleven-team
  event uses two physical 64 GB, 20-thread hosts with measured safe Docker
  allocations of 49152 MiB on the primary and 51200 MiB on the worker, while
  retaining 20% memory headroom.
- **Install from the offline release bundle** (the supported cold path):
  download every asset of the latest release, assemble the bundle directory
  exactly as its release notes show, then from a repo checkout run
  `python -m ridge.offline_install <bundle-dir> <install-dir>` — it
  hash-verifies everything, loads all images, materializes all five asset
  trees, creates the four custom-image build receipts required by `up`, and
  writes `runtime-local.example.json` plus an install receipt.
- Run all later commands from `<install-dir>/source`. Copy
  `<install-dir>/runtime-local.example.json` to the runtime directory and only
  replace its LAN-IP placeholder; its asset paths are already complete.
  Note: `v0.9.0-drill` predates `release-vault.tar.gz`; on that release copy
  `work/release/controller/releases` from a build host into
  `assets/release-vault`, or the first follow-up ticket fails mid-event.
- Participant laptops on the same LAN; no internet required after this point

(Building images from source instead — `python -m ridge.deploy build
--component all && python -m ridge.deploy verify-build` — only makes the
container images, not the content assets; the full content pipeline is a
developer path documented in `docs/handoff/BUILD-FIRST.md`. Event hosts
should use the bundle.)

## 1. Current two-host profile (one-time preparation)

From `<install-dir>/source`, copy
`deployment/profiles/example-dynamic-two-host-11-team.json` to
`../event-profile.json`. It contains exactly 33 slots: `desktop-slot01` through
`desktop-slot14` on the primary and `desktop-slot15` through
`desktop-slot33` on `worker-02`, using worker VNC ports 5901–5919. Edit only:

- `event.event_start` / `duration_minutes`
- `addresses`: set `central_bind_ip` to `<LAN-IP>` and use
  `https://iris.cyberexperts.org`, `https://ctfd.cyberexperts.org`, and
  `https://guac.cyberexperts.org` for the three public URLs. Wazuh uses
  `https://wazuh.cyberexperts.org`.
- the worker address only if it is not `192.168.1.3`;
- declared capacity only after measuring a different host.

For the dynamic profile, do **not** add a roster and do **not** pass `--teams`:
the registration page admits the profile's validated `max_teams`. The current
Compose pool and profile contain 33 exact slots, so they represent at most
eleven teams. This is capacity-valid, not yet performance-certified; retain
that qualification until the human/load rehearsal passes. Each registered team
gets five participant seats and three GUI-only desktop slots. The landing page
is `https://ctfd.cyberexperts.org/silent-ridge/register`.

## 2. Primary runtime local.json (one-time preparation)

Copy `deployment/examples/two-host-11-team.local.example.json` to
`R/local.json`. It already contains the `worker-02` Docker context, worker asset
paths, all 20 Guacamole relay mappings, and the normal external-TLS shape. Edit:

- `bind_ip` and asset paths for the installed primary;
- the worker asset and VNC-password paths if its installation differs;
- `guacamole_relay.source_cidr` to the measured Docker network containing
  `guacd`;
- the wildcard full-chain and private-key paths.

The relevant top-level structure is:

```json
{
  "bind_ip": "<LAN-IP>",
  "assets": {
    "evidence_public": "<abs path>/assets/evidence-public",
    "release_vault": "<abs path>/assets/release-vault",
    "case_template": "<abs path>/assets/case-template",
    "originals": "<abs path>/assets/originals",
    "wazuh_config": "<abs path>/assets/wazuh-config"
  },
  "ports": {"crl": 8080, "iris": 8081, "ctfd": 8083, "guac": 8082,
            "wazuh_dashboard": 8443, "wazuh_indexer": 9200},
  "index_name": "silent-ridge-oct26",
  "tls": {"mode": "external", "certificate": "...", "key": "..."},
  "desktop_workers": {"worker-02": {"docker_context": "ridge-worker-02"}}
}
```

Do not remove the full worker/relay maps from the reusable example. The
abbreviated object above is orientation only.

Keep the `wazuh_config` directory and the runtime secrets from the same
generation (it embeds the hashed admin password; a mismatch fails with
HTTP 401 from the indexer job). After first boot, editing the file or secret
and restarting does **not** rotate the live security-index credential. Use
[Wazuh admin rotation](wazuh-admin-rotation.md) during maintenance instead.

## 3. Prove the installation before event day

```bash
python -m ridge.deploy doctor --profile event-profile.json --runtime R
python -m ridge.deploy up --profile event-profile.json --runtime R
# re-run `up` until every stage verifies
python -m ridge.deploy status --profile event-profile.json --runtime R   # expect event_ready: true
```

`up` stops at a verified, **paused** state — participants see nothing yet.
Before the event, set and securely retain `RIDGE_BACKUP_KEY` (at least 16
characters). Doctor reports a missing key under `recovery_ready` rather than in
`ready_for_up`: the key is not an input to `up`, so a first deployment is
legitimately ready without it. Backup and restore require the same value.
Do not put it in `local.json`, the repository or the recovery set.
On Windows, backup and restore run OpenSSL from the already loaded
`silent-ridge-integration:dev` image with no network or image pull; a host
`openssl.exe` installation is not required. Keep the exact image and backup
key available during recovery.
The host-side registration worker starts automatically when `start` succeeds.
Registration uses one stable room code, `SILENT-RIDGE`, as its only check-in
gate. The opening deck and facilitator runbook both display it. Each team receives
a private retrieval link containing its IRIS, CTFd, and Guacamole credentials
plus the exact names of its three role-specific desktop connections. Do not hand out
`R/secrets/team-credentials.json`; it remains an operator recovery artifact.

The normal current-event path uses the pre-issued
`*.cyberexperts.org` certificate with `tls.mode: external`. All four public
names resolve locally to the primary and use port 443; no participant CA
installation or Internet access is required on event day.

Generated TLS is a fallback only. If external TLS cannot be used, after `up`
generates the final certificates and before any participant login, run
`python scripts/export_participant_ca.py --runtime R --output <new-pack>`.
Follow [participant CA trust](participant-ca-trust.md): distribute the public
certificate over a trusted offline channel, independently verify its SHA-256
fingerprint on each client, and check that all four HTTPS URLs open without a
certificate warning. Keep `http://<LAN-IP>:8080/root-ca.crl` reachable from
participant devices; it is the signed offline CRL embedded in every generated
participant certificate. Do not ask participants to click through TLS warnings
or disable revocation checks.

Certificate installation and local name resolution are detailed in
[public HTTPS certificates](external-tls.md). The certificate must already be
valid and the names must resolve locally before the reboot acceptance test.

## 4. Normal event-day start: no commands

Power on the worker first, then the primary. Boot automation waits for both
Docker engines, runs the safe `up`/`start` sequence, and retries bounded
failures. Do not also run `doctor`, `up`, `status`, or `start`. If the
registration page does not appear, give the operator
`C:\ProgramData\SilentRidge\logs\primary-boot.log` and use this sheet only for
operator recovery.

Project opening slide 5. It contains both the registration address and code:

```text
https://ctfd.cyberexperts.org/silent-ridge/register
SILENT-RIDGE
```

An operator may check registrations while diagnosing a problem:

```bash
python -m ridge.deploy registration-status --profile event-profile.json --runtime R
```

Participant URLs in generated-CA mode (all in their own laptop browser):
`https://<LAN-IP>:8082` desktops · `:8081` IRIS · `:8083` CTFd ·
`https://<LAN-IP>:8443` Wazuh. In external public-TLS mode, all four use
their configured hostnames on port 443; see [public HTTPS certificates](external-tls.md).
Certificate revocation: `http://<LAN-IP>:8080/root-ca.crl` (signed CRL only).

Opening briefing: project **`docs/event-day-deck/opening-brief.pptx`** in
PowerPoint. Use slides 1–3 for the scenario and workflow, play the embedded
introduction on slide 4, then leave slide 5 projected while teams use the
participant landing page.

Closing briefing: project **`docs/event-day-deck/closing-brief.pptx`**. Slide 2
plays the embedded final assessment and slide 3 reveals the winner. Replace the
team-name placeholder before presenting or announce the name live.

LibreOffice operators must use `opening-brief.odp` and `closing-brief.odp`.
Both native ODP files contain the same embedded MP4 media. Test opening slide 4,
closing slide 2, and room audio before participants arrive.

## 5. During the event

```bash
python -m ridge.deploy status --profile event-profile.json --runtime R
python -m ridge.cli --state R/state/state.sqlite announce --operator EXCON --text "..."
python -m ridge.deploy pause --profile event-profile.json --runtime R   # freeze the clock
python -m ridge.cli --state R/state/state.sqlite recover T03 --team team-03 --generation 1 --operator EXCON --reason "..."
```

Use one recovery procedure for a lost private page. Do not register a second
team and do not invent or reset passwords:

```bash
python -m ridge.deploy registration-status --profile event-profile.json --runtime R
python -m ridge.deploy registration-rotate-link --registration-id 3 --profile event-profile.json --runtime R
```

Identify the existing team in `registration-status`, rotate that registration's
link, and send the newly printed private return URL directly to the captain.
The old URL is invalid. The captain downloads the labelled handout, distributes
one of the five individual CTFd seats to each teammate, and uses the labelled
IRIS, Wazuh, Guacamole, and desktop details from that handout. Never give
participants `R/secrets/team-credentials.json`.

For a provisioning failure, repair the named service and retry the same
registration so its reserved slots and generated credentials are preserved:

```bash
python -m ridge.deploy registration-retry --registration-id 3 --profile event-profile.json --runtime R
# Cancel only when the team is abandoning the slot:
python -m ridge.deploy registration-cancel --registration-id 3 --profile event-profile.json --runtime R
```

Symptom → action table: `docs/runbook.md`.

## 6. Capacity rehearsal (before event day, never during participant play)

```bash
PYTHONPATH=. python -m expanded.load --config f03-config.json --duration 1800 --output work/f03/event-run
```

Config template and acceptance checks: `docs/f03-rehearsal.md`. The 33-slot
profile is representable and passes declared capacity validation, but eleven
teams remain performance-uncertified until an eleven-team human/load run passes
on the two event hosts. Include a manual desktop usability pass in parallel.

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
