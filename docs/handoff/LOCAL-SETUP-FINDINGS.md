# Local setup findings: running the handoff on a Windows workstation

**Status:** findings report — no runtime change is proposed here.
**Date:** 2026-09-16
**Baseline:** `main` `370ff50`.
**Method:** the handoff entry point ([README.md](README.md)) and the content-recovery
steps in [CONTINUE-ELSEWHERE.md](CONTINUE-ELSEWHERE.md) were executed in order on a
single Windows workstation, then the central Compose stack was brought up manually
to find where the documented path ends.

All credentials below are throwaway local development values and are not repeated
here. Nothing was committed except this report; the environment was returned to
`main` and the containers, network, volumes and images were removed afterwards.

## 1. Environment

| Item | Value |
|---|---|
| OS | Windows 10/11 workstation |
| CPU / RAM / disk | i7-10510U (4C/8T) / 19.6 GiB / ~365 GB free |
| Docker | Docker Desktop 4.81.0, engine 29.6.1, Compose v5.2.0 |
| WSL | WSL 2.7.3 (`Ubuntu-24.04`, `kali-linux`, `docker-desktop`) |
| Python / Git / Git LFS | 3.12.4 / 2.54.0 / 3.7.1 |

## 2. Results

| Step | Command | Result |
|---|---|---|
| 0 | `git --version`, `git lfs version`, `python --version` | PASS |
| 1 | `python -m unittest discover -s tests` | PASS — 73 tests, OK |
| 2 | `python -m ridge.desktop_image --destination work/desktop.qcow2` | FAIL until `git lfs pull`; PASS after — assembled 4,986 MiB |
| 3 | `python -m expanded.materialize_native --verify-only` | PASS — `archive_verified: true`, 19 files |
| 4 | `python -m expanded.materialize_native --destination work/native-preparation` | PASS — 19 verified originals |
| 5 | `python expanded/author.py` | PASS |
| 6 | `python expanded/prepare.py work/artifacts/new-release` | PASS |
| 7 | `python -m ridge.cli init …` and `status` | PASS — state created, 15 pending |
| 8 | `python -m ridge.cli provision --operator EXCON-A` | FAIL — preflight requires `iris_login`/`ctfd_name` |
| 9 | `.\ridge.ps1 prepare/up`, `python -m ridge.deploy` | FAIL — not implemented on `main` |

**Conclusion:** the content-recovery half of the handoff runs end-to-end on this
PC. The deployment half does not exist on `main`; the one-command interface is
documented as a proposal, and the central stack can only be brought up manually.

## 3. Findings

### 3.1 The desktop image needs its multi-gigabyte LFS parts first (expected)

Without the desktop parts materialised, assembly fails closed with:

```
Desktop assembly failed: Corrupt desktop part: assets/large/desktop/silent-ridge-desktop-v1.qcow2.part001
```

`git lfs pull` of `assets/large/desktop/*` (about 5.2 GB across six parts) resolves
it. This matches the handoff note that the full clone "downloads several
gigabytes", but the failure message reads like corruption rather than "part not
fetched". A clearer message would help a new operator.

### 3.2 Preflight blocks on missing application identities (known, by design)

```
File "ridge/preflight.py", line 25, in check
ValueError: Record expected iris_login and ctfd_name for every team
```

This is blocker #2 in [ASSESSMENT.md](ASSESSMENT.md): `expanded/config.json` ships
with placeholder IDs and no per-team `iris_login`/`ctfd_name`. Accounts must be
provisioned and mapped before delivery can be enabled.

### 3.3 The one-command deployment interface does not exist on `main`

`ridge.ps1`, `profiles/` and the `ridge.deploy` module are absent; the handoff
README labels these commands "a proposed interface, not existing functionality".
`python -m ridge.deploy` fails with `No module named ridge.deploy`.

### 3.4 The central Compose stack runs, but needs two undocumented fixes

The stack (`deployment/expanded/compose.central.yaml`) was brought up by hand with
a local env file, an external `central` network and the three locally built images
(`Dockerfile.iris`, `Dockerfile.ctfd`, `Dockerfile.integration`). CTFd started
cleanly. IRIS failed to boot twice, for two reasons not documented anywhere in the
repository:

1. **`gen_random_uuid()` is missing.** The pinned database image
   `ghcr.io/dfir-iris/iriswebapp_db:v2.4.20` is **PostgreSQL 12.22**, where
   `gen_random_uuid()` lives in the `pgcrypto` extension. The image initialises
   with only `plpgsql`, so the IRIS migration aborts:

   ```
   sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedFunction)
   function gen_random_uuid() does not exist
   ```

   Fix: `CREATE EXTENSION IF NOT EXISTS pgcrypto;` in the application database
   before the first boot (or an init script in the DB image). Upstream IRIS
   deployments normally arrange this; the repository's Compose does not.

2. **The admin role must be the actual superuser.** The DB image creates only
   `POSTGRES_USER` (`iris`) as a superuser; setting `POSTGRES_ADMIN_USER=postgres`
   leaves the app failing with:

   ```
   sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
   FATAL: password authentication failed for user "postgres"
   ```

   The image log shows `Creating database role: postgres`, but the role is not
   present in `pg_roles`. Setting `POSTGRES_ADMIN_USER`/`POSTGRES_ADMIN_PASSWORD`
   to the same superuser the image actually created lets IRIS boot.

Neither fix is in the repository. Both belong in the central provisioning work
(tasks B01/B04) and should be encoded in Compose or an init script rather than
left to an operator.

### 3.5 Observations for the desktop pivot

The container-desktop proposal (see PR #14 / PR #18) removes the VM, QCOW2,
`qemu-img`, Hyper-V and the AWS AMI from the critical path. On this host the
Docker engine exposes ~9.5 GiB, so a manual stack plus one or two Autopsy desktops
is the practical ceiling; the ten-team event needs a larger or multi-host Docker
environment.

## 4. Minimal manual central-stack recipe (sanitized)

This is the working sequence discovered above, with values redacted:

```text
# 1. Build the three application images
docker build -f deployment/expanded/Dockerfile.iris        -t silent-ridge-iris:dev .
docker build -f deployment/expanded/Dockerfile.ctfd        -t silent-ridge-ctfd:dev .
docker build -f deployment/expanded/Dockerfile.integration -t silent-ridge-integration:dev .

# 2. Pull the pinned dependency images (Compose uses pull_policy: never)
docker pull rabbitmq:3-management-alpine
docker pull mariadb:10.11
docker pull redis:7-alpine
docker pull ghcr.io/dfir-iris/iriswebapp_db:v2.4.20

# 3. Create the external network and a private env file
docker network create silent-ridge-central
#    env file sets IRIS_IMAGE/CTFD_IMAGE, *_ENV_FILE, secrets, ports, and
#    POSTGRES_ADMIN_USER = the superuser the DB image actually created

# 4. Bring up the stack
docker compose --env-file <private>.env -f deployment/expanded/compose.central.yaml up -d

# 5. One-time database fix before IRIS can migrate
docker exec <iris-db> psql -U <superuser> -d <app_db> -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
docker restart <iris> <iris-worker>
```

## 5. Recommended follow-ups

| Finding | Where it belongs |
|---|---|
| Encode `pgcrypto` creation in the DB init | B01 (IRIS bootstrap) / B04 (Compose) |
| Document that `POSTGRES_ADMIN_USER` must match the created superuser | B01 / B04 |
| Clearer "LFS parts not fetched" message in `ridge.desktop_image` | small follow-up |
| A real one-command `up` with a private profile | E01/E02, B05 |
| Provisioning identities so preflight passes | B01/B02 |

## 6. Not tested

- No participant session, claim, answer, finding, point or closure was exercised
  end-to-end against the live stack.
- Wazuh was not part of this bring-up (the stack and certificates are not
  vendored).
- Guacamole and a desktop were not started; no Autopsy/Cutter GUI check ran.
- No multi-team load or capacity measurement was performed.

## 7. Reproducibility

All commands run from the repository root on `main` `370ff50`. The content-recovery
steps (1–7 in the results table) are repeatable from a clean checkout with Git LFS
available. The central-stack steps in section 4 are a local, throwaway recipe and
must not be used with real credentials.
