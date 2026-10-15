# Two-team pilot receipt — first successful local bring-up on this host

Date: 2026-09-29. Branch: `fix/bounded-http-503-reset` (uncommitted working change).
Baseline: `main` `4203239` plus four defects fixed in the working tree.
Branch: `fix/bounded-http-503-reset` — commit `c675ac8` (HTTP fix, pushed never)
plus an uncommitted Wazuh group.
Runtime: `work/runtime-pilot` (private; holds secrets, state, certificates).
Profile: `work/profiles/pilot-2team.json` (private; outside Git via `.gitignore`).

**Status:** the stack is `PROVISIONED_PAUSED` and every stage verifies. It is
**paused**, as an `up` must be. This is not an event: nothing has been started,
no participant has connected, no ticket has been claimed, and no question has
been answered. See §5 for what remains unproven.

## 1. Result

`python -m ridge.deploy status` reports `event_ready: true` with all seven
stages verified:

| Stage | Verified detail |
|---|---|
| `PREFLIGHT` | images and content assets present |
| `INFRASTRUCTURE_READY` | 9 services |
| `APPLICATIONS_READY` | 6 services |
| `IDENTITIES_READY` | 2 inventories (IRIS, CTFd) |
| `DESKTOPS_READY` | 2 desktops, 2 Guacamole connections |
| `EVIDENCE_READY` | index `silent-ridge-oct26`, **505 documents** |
| `PROVISIONED_PAUSED` | mode `paused`, **2 teams**, **20 tickets**, 0 pending |

Live participant-facing checks, all served over the local CA:

| Endpoint | Result |
|---|---|
| `https://192.168.1.200:8081/login` (IRIS) | HTTP 200 |
| `https://192.168.1.200:8083/login` (CTFd) | HTTP 200 |
| `https://192.168.1.200:8082/guacamole/` | HTTP 200 |
| `https://192.168.1.200:8443/` (Wazuh dashboard) | HTTP 302 |
| `http://192.168.1.200:8080/root-ca.crl` | HTTP 200 |

16 containers running; all except the Wazuh dashboard and Guacamole report a
healthcheck, and both of those are serving HTTP as verified above.

Full test suite after all four fixes: **395 tests, OK, 22 skipped**.

## 2. Four real defects, all in the Wazuh bring-up path

None of these were visible from the unit suite — every one only appears when a
real stack is composed. The Wazuh stack had apparently never been brought up
from this branch on a clean host.

### 2.1 Cert filename mismatch — indexer would not start

`generate-certs.sh` emits `indexer.pem` / `indexer-key.pem`, but the pinned
upstream `wazuh.indexer.yml` addresses its TLS material as
`wazuh.indexer.pem` / `wazuh.indexer.key`. The indexer crash-looped on
`OpenSearchSecurityPlugin` →
`Unable to read /usr/share/wazuh-indexer/certs/wazuh.indexer.pem`.

The `wazuh-indexer-certs-init` container exited 0 while producing a certificate
volume the indexer could not use: nothing checked that the names the config
requires were the names the init published.

Fix: `wazuh-indexer-certs-init` now also publishes the upstream names as copies,
so the digest-pinned vendored config is used unmodified.

### 2.2 Same mismatch — dashboard would not start

`wazuh-dashboard` reads `/usr/share/wazuh-dashboard/certs/wazuh-dashboard-key.pem`
while the init published `dashboard-key.pem`. The dashboard died with
`ENOENT` → `fatal`.

Fix: `wazuh-dashboard-certs-init` publishes `wazuh-dashboard*.pem` as well.

### 2.3 Service rename broke the indexer DNS name

The repo renamed upstream's `wazuh.indexer` service to `wazuh-indexer`, but the
pinned `opensearch_dashboards.yml` and `wazuh.indexer.yml` both address it as
`wazuh.indexer`. The dashboard logged
`[ConnectionError]: getaddrinfo ENOTFOUND wazuh.indexer` every few seconds and
never became healthy.

Fix: publish the upstream name on the shared backend network
(`aliases: [wazuh.indexer]`) and set `hostname: wazuh.indexer`. The alias is
what makes it resolvable; the hostname alone would not have.

### 2.4 Hardcoded loopback broke the dashboard API call

`_apply_evidence` in `ridge/deploy/local.py` built the dashboard URL as
`https://127.0.0.1:<port>`. Services are published on `local.json`'s `bind_ip`,
so on a host bound to a LAN address nothing listens on loopback and `up` died
with `URLError: [WinError 10061]`.

Fix: use `_dashboard_bind_ip()`, which the class already exposes and which
validates the address. This is the only other hardcoded `127.0.0.1` in the
module; the remaining one is the documented loopback default for `bind_ip`.

## 3. A self-inflicted mistake worth recording

The first attempt at the 2.3 fix put a `#` comment inside a `>-` folded YAML
scalar. `>-` joins lines with spaces, so the comment swallowed every command
after it. The init container still exited 0, the alias was silently never
created, and the symptom was identical to before the fix — which is what made me
check the resolved command rather than assume the edit had applied:

```
"done; # The pinned upstream wazuh.indexer.yml addresses ... # unmodified. cp /source/..."
```

The fix is now commented in YAML above the key, not inside the scalar, and both
init commands carry a warning not to reintroduce a `#`.

## 4. Content assets had to be produced first

A source build produces container images only. `up` additionally requires five
content asset trees in `local.json`, and none of them exist in a fresh clone:

| Asset | How it was produced |
|---|---|
| `evidence_public` | `python -m expanded.prepare work/artifacts/pilot` → `initial/` |
| `release_vault` | same run → `controller/releases/` |
| `case_template` | `python -m ridge.case_template` (verifies the published archive) |
| `originals` | `python -m expanded.materialize_native` (19 verified originals) |
| `wazuh_config` | **not in the repo** — see below |

`wazuh_config` is the notable gap. `deployment/expanded/wazuh/` vendors only the
project's own overlay; `compose.wazuh.yaml` mounts upstream
`wazuh.indexer.yml`, `internal_users.yml`, `wazuh_manager.conf` and
`opensearch_dashboards.yml`, and `preflight` fails if they are absent. They are
normally materialized by `ridge.offline_install` from the release bundle, so the
**source path has no documented way to obtain them**. I fetched them from the
exact commit pinned in `manifest.json`
(`574c7b05c747499e6af31a1ba8a33abebee1f298`) via a new
`scripts/fetch_wazuh_config.py`, which prints each file's SHA256 so the
retrieval is auditable. That script is a developer-path convenience, not a
verified event path, and is flagged as a follow-up.

Third-party images also must be pre-pulled because every compose file sets
`pull_policy: never`. `nginx:alpine` was missing and had to be fetched; the rest
were present.

## 5. Honest limits — what is NOT proven

- **Paused, not started.** `start` was never run. No clock, no participants, no
  ticket claims, no answers, no points. `event_ready: true` reflects the
  bring-up gates only and must not be read as an accepted event.
- **No browser session was verified.** IRIS, CTFd, Guacamole, the dashboard and
  the CRL were each confirmed to return a valid HTTP response. Nobody has
  actually logged in through Guacamole, opened the WS17 Autopsy case, searched
  it, or opened the PCAP in Cutter. Those are the N2/F03 gates and are untouched.
- **Wazuh dashboard and Guacamole report no healthcheck** in
  `docker ps`; they are verified by HTTP response instead.
- **Single host, single run, Windows only.** None of the four fixes has been
  exercised on Linux or macOS.
- **The two "healthy-by-http" containers deserve a second look** on event day;
  a 302 from the dashboard is a redirect, not a verified signed-in session.
- **The 15.5 GiB Docker memory cap was not raised.** This fits 2 teams. It is
  still the blocker for the 10-team rehearsal.
- **No backup or restore was tested.** `recovery_ready` remains false.
- **Split across two commits on one branch, nothing pushed.** `c675ac8` holds the
  `bounded_http` fix and the clean-baseline receipt; the Wazuh fixes,
  `fetch_wazuh_config.py` and this receipt are still uncommitted in the working
  tree. The branch is `fix/bounded-http-503-reset`, and the second commit will
  make it a two-topic branch — the organizer may prefer to split it.
