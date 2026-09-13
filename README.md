# Operation Silent Ridge — October 2026 cyber lane

A runnable cooperative CND/DFIR exercise for five SOC cells investigating disclosure
of a fictional patrol's movement information. Includes handouts, facilitator solutions,
three injects, reproducible synthetic evidence, Jira import data and Docker services.
All activity is defensive and confined to synthetic training data.

**Facilitator answers are public in this repository.** Give participants only the
portal and released handouts, never the repository ZIP or host/Docker access. For
a blind assessment, prepare and rehearse a private variation.

## Setup and startup

Prerequisites: Git, Python 3.12 or later, and Docker Engine with Compose v2 using
Linux containers. No pip packages are needed. Windows: substitute `py -3.12` or an
actual interpreter path if `python` is an inactive Store alias. Run all commands
from the repository root. Review config.json before initialization: 15 October,
180 minutes, 20 people and injects 35/75/115 are configurable planning assumptions.

```text
git clone https://github.com/Judge-M/Oct26.git
cd Oct26
python -m unittest discover -s tests -v
python scripts/exercise.py init
python scripts/exercise.py verify
docker compose config --quiet
docker compose pull gateway
docker compose build
docker compose up -d --wait
docker compose ps
```

Use current main or a validated release tag. Open [the local portal](http://127.0.0.1:8080). The controller reads
runtime/cell-logins.txt locally and privately gives each cell only its own line.
Choose network, endpoint, identity, server or hunting on the login page and enter
that cell's password. Use the **Open [cell] tab** links to sign in as all five cells
in one browser. Each link opens an independent tab; a visible label and tab title
identify the active cell. **Switch cell / Sign out** affects only that session.
Sessions survive refresh, expire after eight hours, and require a new login after
a server restart. Passwords are not saved by the application. Use these links
rather than the browser's Duplicate Tab feature, which may copy session storage.
Do not paste
credentials into tickets, Git or screenshots. Config changes require a new run.

For multiple seats, create an ignored .env containing `BIND_IP=<training-interface-ip>`
and optionally `PORT=8080`. Recreate with `docker compose up -d --wait`, restrict
the host firewall to the lab subnet and distribute `http://<training-host>:8080`.
HTTP authentication requires an isolated lab network; use locally managed
TLS if crossing a shared network. Do not expose the service publicly.

Portable fallback after the same init/verify commands:

```text
python app/server.py
```

It listens on loopback port 8080. For approved lab access use
`python app/server.py --host <training-interface-ip>`. Stop with Ctrl+C. Do not run
portable and Docker modes against the same state or port simultaneously.

## Participant distribution and operation

Participants download the three handouts and initial evidence through the portal,
verify SHA256SUMS.json, and analyze working copies. Every cell can see all evidence
and tickets. Native PCAP/SQLite are supplied where practical; collection notes label
simplified CSV/JSONL and reconstructed sensor traffic. No executable is supplied.
Jira is the intended work surface: follow [Jira setup](docs/jira.md). Choose Jira
or the built-in rehearsal board as the authoritative record before starting.

Controller materials: [event plan](docs/event-plan.md),
[ground truth](facilitator/ground-truth.md), [controller guide](facilitator/controller-guide.md),
[solutions](facilitator/solutions.md), [assessment and AAR](facilitator/assessment-aar.md).
At each scheduled elapsed time, run the corresponding release, then verify:

```text
python scripts/exercise.py release 1
python scripts/exercise.py verify
```

Repeat with `release 2` and `release 3` only when due. Do not release all three at
startup. Announce deadlines and ask cells to refresh. Releases are ordered and
idempotent. Recommendations go through exercise control and need written simulated
acknowledgment; participants never direct real personnel.

## Verification

```text
python -m unittest discover -s tests -v
python scripts/exercise.py verify
docker compose config --quiet
docker compose ps
docker compose logs --tail 50
```

Tests cover evidence determinism and consistency, PCAP/SQLite validity, access
boundaries, shared comments, status ownership, inject gating, persistence, export
and reset. See [validation record](docs/validation.md) for executed checks and gaps.
On a rehearsal run only, `python scripts/smoke.py` tests the deployed HTTP service
and writes a test comment. After restart, use `python scripts/smoke.py --expect-persistence`.
After release 1, also pass `--released`. It expects a clean run on its first invocation.

Before live use, verify each participant seat can download/hash evidence, comment
on another cell's ticket and see retained comments after restart. Check that future
inject paths return 404. Rehearse actual Jira permissions and export separately.
If Docker reports a missing engine pipe, start Docker Desktop with Linux containers
and check virtualization/WSL; use portable mode while resolving the host requirement.
For /state permission failures, see [architecture](docs/architecture.md). Never fix
access by mounting the repository or vault. Reset rotates credentials.

## Export, shutdown and reset

Pause inject releases, then:

```text
python scripts/exercise.py export
docker compose down
```

For portable mode use Ctrl+C instead of Compose down. Ignored exports/run-<UTC>.zip
contains a coherent SQLite snapshot, released evidence, config and release log,
excluding credentials. Export Jira work including comments separately if authoritative.
Keep all participant work private. For a new run, after stopping the service:

```text
python scripts/exercise.py reset --stopped
python scripts/exercise.py verify
docker compose up -d --wait
```

Reset exports and archives the old runtime under ignored exports/, then creates only
initial evidence and new credentials. The full runtime archive contains old passwords;
keep it controller-only. Nothing is recursively deleted. --stopped is your attestation,
not automatic process detection. Do not reset a running service. Set archive retention
with the event owner.

To generate a separate bundle without starting a run:

```text
python scripts/generate.py build/rehearsal-evidence
```

The destination must not exist. Distribute initial/ only; inject directories stay
private until release. Identical sources/config/runtime produce identical hashes.
SQLite bytes can vary across runtime versions; archive tool versions and each build's
manifest. Runtime, credentials, exports and student data are excluded from Git and
the Docker image. See [architecture and access control](docs/architecture.md).

## Decisions before live rehearsal

Confirm date, duration, count/skills, staff, hardware/virtualization, network/TLS,
Jira project and permissions or fallback, public-answer exposure, accessibility and
retention. Optional narrative connections for other instructors are in the event
plan; the cyber lane depends on no other lane's products.


## Controller records, timing and offline restoration

Run `python scripts/schedule.py` before initialization. Set duration_minutes to 120
or 180 to select a validated schedule; all deadlines and inject headings are rendered
from that schedule. Read [controller ledger](docs/controller-ledger.md) for named
acknowledgments, clock start/pause/resume, comment IDs and export traceability.
Read [offline deployment](docs/offline.md) to package both exact images plus the
controller source/configuration and restore without a build or network pull.
