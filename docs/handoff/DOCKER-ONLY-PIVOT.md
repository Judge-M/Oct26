> Historical proposal/inventory from PRs 14/18. Current instructions: [BUILD-FIRST.md](BUILD-FIRST.md).
> Do not treat old host capability claims, missing hashes or design decisions below as current acceptance.

# Docker-only desktop pivot: findings and requirements

**Status:** proposal for review — nothing implemented, nothing merged.
**Date:** 2026-09-16
**Baseline:** upstream `main` `370ff50` (merged PR #6).
**Scope:** replace the per-team Ubuntu VM desktop with a per-team container, and
run the whole exercise — central services *and* desktops — on Docker only.
**Related:** `ASSESSMENT.md`, `EXECUTION.md`, `TASKS.md`, `docs/desktop-image.md`,
`docs/expanded-deployment.md`, `deployment/expanded/versions.json`.

---

## 1. Executive summary

- The current design needs a hypervisor (QEMU/KVM, Hyper-V, VirtualBox or AWS) for
  one 30-GiB Ubuntu desktop per team. That is the only non-Docker component.
- Guacamole's `guacd` already reaches each desktop as plain VNC at
  `hostname:5901` on an external `desktop` network
  (`deployment/expanded/compose.guacamole.yaml:7,12`). A container that exposes
  5901 is therefore a drop-in replacement for the VM.
- Pivoting to a container desktop removes the QCOW2 image, `qemu-img`, Hyper-V,
  VirtualBox, cloud-init, `seal-image.sh` and the AWS AMI path from the critical
  path. Everything else is already Docker.
- The pivot is a real architecture change: it re-scopes task **C01** (desktop
  provider) and **C03** (evidence delivery), and makes **H01c/H01d** and **E03**
  optional. It should be recorded as a decision before dependent work continues.
- **Capacity, not software, is the remaining constraint.** This PC's Docker
  engine has ~9.5 GiB RAM; an Autopsy desktop wants ~2–4 GiB. It can prove one or
  two team desktops, not the ten-team event.

---

## 2. Verified environment inventory (this PC)

Checked 2026-09-16 with `docker`, `wsl`, `Get-CimInstance`, `Get-ItemProperty`.

### 2.1 Present

| Item | Version / detail |
|---|---|
| Docker Desktop | 4.81.0; engine 29.6.1, driver `overlayfs`, daemon reachable |
| Docker engine resources | 8 CPU, **10,217,435,136 bytes (~9.5 GiB)** RAM |
| Docker Compose | v5.2.0 |
| VirtualBox | 7.2.8 (`VBoxManage` available) |
| WSL | 2.7.3; distros: `docker-desktop` (running), `Ubuntu-24.04`, `kali-linux`, `podman-machine-default` |
| Ubuntu-24.04 WSL | 24.04.4 LTS; `python3`, `docker`, `git` (no `qemu-img`, `gcc`, `make`, `VBoxManage`) |
| Java | Temurin 21.0.4 LTS |
| Git / Git LFS | 2.54.0 / 3.7.1 |
| Python | 3.12.4 |
| Host CPU | Intel i7-10510U, 4 cores / 8 threads |
| Host RAM | 19.6 GiB |
| Host disk | 365.7 GB free on `C:` |
| Git LFS assets | training binary, native capture, autopsy case v1/v2 fetched |

### 2.2 Not present / not usable

| Item | Note |
|---|---|
| Autopsy / Wireshark / Cutter on Windows host | Not needed on the host — they live inside the desktop image |
| `qemu-img` | Not in Windows or either WSL distro |
| `gcc` | Not in Windows or either WSL distro |
| AWS CLI | Absent (only relevant to the AWS provider, now optional) |
| Hyper-V from this shell | `Get-VM` → permission denied; use Docker (and VirtualBox if ever needed) |
| Desktop QCOW2 | Only LFS pointer files; 5.2 GB not materialized |
| Pinned application images locally | Only `ctfd/ctfd:3.8.2`, `mariadb:10.11`, `redis:7-alpine` present |

### 2.3 Registry reachability (verified via `docker manifest inspect`)

All pinned images resolve from this network — nothing has to be sourced elsewhere:

```
OK  ghcr.io/dfir-iris/iriswebapp_app:v2.4.20
OK  ghcr.io/dfir-iris/iriswebapp_db:v2.4.20
OK  ctfd/ctfd:3.7.7
OK  guacamole/guacamole:1.5.5
OK  guacamole/guacd:1.5.5
OK  wazuh/wazuh-indexer:4.9.2
OK  wazuh/wazuh-dashboard:4.9.2
OK  wazuh/wazuh-manager:4.9.2
OK  rabbitmq:3-management
OK  postgres:16
OK  python:3.12.10-slim
```

### 2.4 Test baseline

`python -m unittest discover -s tests` on `main` `370ff50` → **73 tests, OK**
(Git LFS objects must be fetched first; without them seven evidence tests fail on
a manifest hash mismatch, which is a checkout artifact, not a repo defect).

---

## 3. What the exercise requires (three tiers)

### Tier 1 — central services (Docker host, once per event)

| Component | Pin | Image / source |
|---|---|---|
| IRIS application | 2.4.20 | `ghcr.io/dfir-iris/iriswebapp_app:v2.4.20` + local extension (`Dockerfile.iris`) |
| IRIS database | 2.4.20 | `ghcr.io/dfir-iris/iriswebapp_db:v2.4.20` |
| RabbitMQ | 3.x | `rabbitmq:3-management` |
| CTFd | 3.7.7 | `ctfd/ctfd:3.7.7` + plugin (`Dockerfile.ctfd`), MariaDB 10.11, Redis 7 |
| Integration bridge + worker | — | built from `Dockerfile.integration` (`python:3.12.10-slim`) |
| Wazuh indexer / dashboard / manager | 4.9.2 | official single-node Docker deployment + certificates |
| Guacamole + guacd | 1.5.5 | `guacamole/guacamole:1.5.5`, `guacamole/guacd:1.5.5`, PostgreSQL 16 |
| Controller core | — | Python 3.12 + SQLite (`ridge`) |

### Tier 2 — team desktops (one per team)

Ubuntu 24.04 Xfce with Autopsy 4.22.0 + Sleuth Kit 4.13.0, Cutter 2.5.0 AppImage,
Wireshark, Firefox 140.16.0esr, TigerVNC, Thunar, dbus. Today: a 5.2-GB QCOW2
(30-GiB virtual) on a hypervisor. Proposed: a container.

### Tier 3 — participant client

A web browser only. Guacamole is HTML5; IRIS, CTFd and Wazuh are web UIs. No
client install.

### Preparation-only tooling

Git + Git LFS, Python 3.12, and (for the VM path only) `qemu-img`, `gcc`, Java 21.

---

## 4. Repository readiness findings

The handoff review (`ASSESSMENT.md`, reviewed against `305c257`) found the content
and transactional core are well advanced but the repository is not yet an event
deployment product. Open items, unchanged by this pivot unless noted:

**P0 — blocks the promised event experience**

1. No deployment orchestrator (`ridge/cli.py` manages core state only).
2. `expanded/config.json` is not runnable (placeholder IDs, missing
   `iris_login`/`ctfd_name` required by `ridge/preflight.py:25`).
3. Autopsy path contracts disagreed (`author.py` vs `preflight.py` vs `prepare.py`
   vs the desktop path).
4. No end-to-end desktop delivery contract for follow-up evidence.
5. Central provisioning and Wazuh incomplete (stack/certs not vendored).
6. Ten-team educational capacity unsupported (1,300 team-min → ~130/team, not 260).

**P1 — before event approval**

Single active site / fencing; incomplete recovery (`export_run` is audit-only);
identity portability; run-scoped Compose names/volumes; resource capacity;
storage lifecycle; no published GitHub Release / immutable offline bundle; AWS
readiness and cost (now optional under this pivot).

### 4.1 Work completed by the three agent lanes (unmerged)

Three isolated branches were produced from `main` `370ff50`. Each lane added
source and deterministic tests; **all live acceptance was marked blocked** because
the lanes were (incorrectly) told Docker/Linux/hypervisors were unavailable. That
block is now liftable for everything except hypervisor-specific items.

| Lane | Branch | Result |
|---|---|---|
| Wave 0 (A01–A05) | `lane/wave0` | All five done; 114 tests OK |
| Waves 1–2 (B01–B05, C01–C04, D01) | `lane/wave12` | Source + tests; B05 blocked; 149 tests OK |
| Review + H01 + Waves 3–5 | `lane/review-h01` | Independent review + H01a–e + D02–G01 source; 127 tests OK |

These branches are **not merged and not pushed**. They are a starting point, not
accepted work.

---

## 5. Target architecture (Docker-only)

```
participant browser
        │ HTTP(S)
        ▼
  Guacamole (8080)  ──guacd──►  desktop-teamNN:5901  (VNC, internal network)
        │                             │
        │                             ├─ /evidence, /originals  (read-only volume)
        │                             ├─ /home/participant/Cases (per-team volume, seeded)
        │                             └─ Xfce + Autopsy + Cutter + Wireshark + Firefox
        ▼
  IRIS ── CTFd ── integration bridge ── Wazuh ── controller core
        (all containers, internal networks)
```

- One container per team; one shared X display per container (matches the intended
  "three people share a desktop" model).
- VNC is never published to the host — only `guacd` on the internal `desktop`
  network can reach it. Guacamole terminates the user-facing session.

---

## 6. Requirements to implement the pivot

### 6.1 New artifacts

| Artifact | Purpose |
|---|---|
| `deployment/expanded/desktop/Dockerfile` | Desktop image (adapt `configure-image.sh`) |
| `deployment/expanded/desktop/entrypoint.sh` | VNC password from secret, `Xtigervnc :1`, `dbus-run-session -- startxfce4`, `tini` as PID 1 |
| `deployment/expanded/compose.desktops.yaml` | N desktop services, limits, `shm_size`, volumes, secrets, `desktop` network |
| `ridge/docker_provider.py` | Create/start/stop/probe desktop containers (replaces `hyperv_provider.py`) |
| design note / decision record | This document, once accepted |

### 6.2 Build inputs (one-time, online; then `docker save` for offline)

| Input | Source / pin |
|---|---|
| Autopsy 4.22.0 (Linux) | Sleuthkit/Autopsy release archive; place at `/opt/autopsy` |
| Sleuth Kit 4.13.0 | bundled with Autopsy, or separate |
| Cutter 2.5.0 AppImage | URL + SHA-256 in `assets/desktop-v1.json:58` |
| Firefox 140.16.0esr | URL + SHA-256 in `assets/desktop-v1.json:63` |
| Java runtime | `openjdk-21-jre` / `libopenjfx-java` |
| Ubuntu packages | `xfce4`, `tigervnc-standalone-server`, `dbus-x11`, `thunar`, `wireshark`, `zenity`, fonts, `adwaita-icon-theme`, `tini` |

### 6.3 Code / config changes

| File | Change |
|---|---|
| `deployment/expanded/guacamole.py` | Set each desktop `address` to its container service name (logic already emits `port 5901`) |
| `ridge/desktop_delivery.py` | Target the shared evidence volume + per-team case volumes instead of VM replication |
| `ridge/hyperv_provider.py` | Retire or keep as a fallback; new `docker_provider.py` is primary |
| `assets/desktop-v1.json` | Mark the QCOW2 as an optional fallback; add a container image manifest |
| `docs/desktop-image.md`, `docs/expanded-deployment.md` | Rewrite around the container desktop |
| `deployment/expanded/versions.json` | Add the container base and any new pins |
| `tests/` | Container provider, compose rendering, evidence-mount tests |

### 6.4 Capacity

| Item | Value |
|---|---|
| Tested desktop allocation | 4 vCPU / 8 GiB (VM) |
| Practical container need | ~2–4 GiB per Autopsy desktop |
| This PC's Docker engine | ~9.5 GiB → **1–2 desktops** |
| Ten-team event | ~20–40 GiB just for desktops + central services; needs a larger or multi-host Docker environment |

### 6.5 Offline packaging

Build all images online, then `docker save` the central stack, desktop image and
all upstream dependencies; publish immutable digests and an installable manifest.
Keep secrets and live state outside the image.

---

## 7. Caveats and risks

- **Autopsy/Solr** needs `shm_size` and RAM; keep the existing `SOLR_LOGS_DIR` and
  `SOLR_PID_DIR` handling from `configure-image.sh:18-26`.
- **Firefox sandbox** in a container needs `--no-sandbox` or a seccomp profile.
- **Wireshark** as non-root opens pcaps fine; live capture would need `NET_RAW`
  (not required).
- **Cutter AppImage** uses `--appimage-extract-and-run`, so no FUSE is needed.
- **VNC is unencrypted** — acceptable only on the internal network behind
  Guacamole; never publish 5901.
- **PID 1 / zombies** — use `tini` or a supervisor.
- **Image size** ~2–4 GB; build time is significant.
- **Fidelity** — a container desktop is not the published VM; record the
  difference and keep the VM path documented as an alternative.
- **Licensing** — Autopsy (Apache-2.0) and Cutter (GPL) are redistributable; keep
  notices when baking into the image.

---

## 8. Minimal proof path on this PC

1. Build the desktop image for one team.
2. `docker compose -f compose.desktops.yaml up -d desktop-team01`.
3. Start the Guacamole stack; provision one connection → `desktop-team01:5901`.
4. Browser → Guacamole → Xfce → open the WS17 case in Autopsy and analyze the
   training binary in Cutter.
5. Bring up the central stack (IRIS/CTFd/Wazuh/integration); test one
   claim → answer → finding → point → closure end-to-end.

---

## 9. Decisions needed

- [ ] Adopt the container desktop as the primary design, VM as fallback, or keep
      VM-only? (Recommend: container primary.)
- [ ] Authorise building/pulling the central and desktop images on this host.
- [ ] Confirm the intended desktop session model (one shared session per team vs
      one per participant).
- [ ] Set the event capacity target and the rehearsal host(s) — this PC proves the
      path, not the ten-team load.
- [ ] Confirm whether the AWS path (E03–E05) stays in scope or is deferred.

---

## 10. Re-scoped task mapping

| Task | Effect of the pivot |
|---|---|
| C01 — desktop provider | Re-scope from Hyper-V to Docker containers |
| C03 — evidence delivery | Deliver into volumes instead of VM replication |
| H01c — desktop preparation | Optional (only needed for the VM fallback) |
| H01d — export/verify | Optional |
| E03 — AWS desktop AMI | Deferred / optional |
| E04–E05 — AWS infra/teardown | Deferred / optional |
| B05, D01, D02, D03 | Live acceptance now unblocked on this host |

---

## Appendix A — Verification commands used

```powershell
docker version --format '{{.Server.Version}}'
docker compose version
docker info --format 'OSType={{.OSType}} CPUs={{.NCPU}} MemTotalBytes={{.MemTotal}} Driver={{.Driver}}'
wsl --list --verbose --all
Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select @{n='RAM_GiB';e={[math]::Round($_.TotalPhysicalMemory/1GB,1)}}
Get-PSDrive C
foreach ($i in @('ghcr.io/dfir-iris/iriswebapp_app:v2.4.20','ctfd/ctfd:3.7.7')) { docker manifest inspect $i }
python -m unittest discover -s tests
```

## Appendix B — Key evidence references

- Guacamole reaches desktops via `hostname:5901`:
  `deployment/expanded/compose.guacamole.yaml:7,12`
- Desktop tool/package expectations:
  `deployment/expanded/desktop/configure-image.sh:5-17,27-36,67-84`
- Desktop tool pins and URLs:
  `assets/desktop-v1.json:52-65`
- Pinned versions (candidate, not validated):
  `deployment/expanded/versions.json`
- Central Compose services and required variables:
  `deployment/expanded/compose.central.yaml`
- Base images built from: `deployment/expanded/Dockerfile.iris`,
  `Dockerfile.ctfd`, `Dockerfile.integration`
