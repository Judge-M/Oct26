# Operation Silent Ridge

A cooperative, defensive incident-response exercise for **ten teams of three**.
Participants investigate a fictional breach using real forensics and detection
tools — Autopsy, Wireshark, Cutter and Wazuh — coordinated through a shared
IRIS case, with questions and scoring in CTFd. Teams claim investigation
tickets, submit findings, and earn equal-value points that persist even when a
ticket changes hands. Everything in the scenario is fictional; the evidence,
the tools, and the teamwork are real.

This repository contains the full event: the authored scenario and evidence,
the tooling that builds and runs it, the participant materials, and the
facilitator guides.

## What participants experience

Each team shares one cloud-hosted-in-a-container Linux desktop (three people,
one screen, via Guacamole in a browser — nothing to install). From there they:

1. Claim an investigation ticket in IRIS (the shared incident case).
2. Investigate with the desktop tools: disk images in Autopsy, network
   captures in Wireshark, a suspicious binary in Cutter, logs in Wazuh.
3. Answer the ticket's questions in CTFd. Correct answers post the finding
   back into the shared IRIS case automatically and score one point — so
   every team's work helps everyone else's picture of the incident.
4. Later tickets unlock as their prerequisites are solved, converging on the
   full incident story.

The event is designed for a 4–5 hour day including orientation, a break, and
a facilitated after-action review.

## What you need to host it locally

One machine runs the whole event. Measured on the live stack, plan for:

- **64 GB RAM** (central services use ~6 GB; each team desktop up to 4 GB)
- **16 CPU cores**, **500 GB NVMe SSD**, gigabit LAN for participant browsers
- **Docker** (Docker Desktop on Windows, or Docker Engine on Linux)
- **Python 3.11+** and **Git with Git LFS** for the build host

A smaller machine works for a two-team pilot (32 GB RAM is comfortable).

## Quick start

```bash
git clone https://github.com/Judge-M/Oct26.git
cd Oct26
git lfs pull                                # fetch the evidence assets

python -m ridge.deploy doctor               # check host prerequisites
python -m ridge.deploy build --component all   # build images (downloads dependencies)
python -m ridge.deploy verify-build         # verify the built artifacts
```

Then create a deployment profile — copy `deployment/profiles/example-two-team.json`,
adjust it (event id, dates, desktop count, host addresses), and bring the
event up:

```bash
python -m ridge.deploy up     --profile path/to/profile.json --runtime path/to/runtime
python -m ridge.deploy status --profile path/to/profile.json --runtime path/to/runtime
python -m ridge.deploy start  --profile path/to/profile.json --runtime path/to/runtime
```

`up` builds out the entire stack and stops at a verified, paused state —
nothing is visible to participants until you explicitly `start`. The `runtime`
directory is private: it holds the event's secrets, state, and the team
account inventories you hand out to participants. On Windows, `ridge.ps1`
wraps the same commands (`.\ridge.ps1 prepare / up / status / start ...`).

Participants then connect in a browser (default ports, bound to localhost
unless you set `BIND_IP`):

| What | Where |
|---|---|
| Team desktops (Guacamole) | `http://<host>:8082` |
| IRIS incident case | `http://<host>:8081` |
| CTFd questions and score | `http://<host>:8083` |

## Running the event

```bash
python -m ridge.deploy pause   --profile ... --runtime ...   # pause the clock
python -m ridge.cli announce --operator EXCON --text "..."   # message all teams
python -m ridge.cli recover T03 --generation 1 --operator EXCON --reason "..."
```

Facilitator materials (runbook, solutions, coaching and AAR guides) live in
`facilitator/`; participant worksheets in `participants/`. See
`docs/expanded-operations.md` for the full operator guide.

## Backup, restore, teardown

```bash
python -m ridge.deploy backup  --profile ... --runtime ...   # verified recovery set
python -m ridge.deploy down    --profile ... --runtime ...   # stop; keeps all data
python -m ridge.deploy down --volumes --profile ... --runtime ...   # full wipe
python -m ridge.deploy restore --from <recovery-set> --profile ... --runtime <empty-dir>
```

`backup` produces a checksummed recovery set (databases, state, evidence,
team workspaces, Wazuh index, encrypted secrets). `down --volumes` is
destructive and **refuses to run unless a verified backup exists**. Restore
onto an empty runtime directory replays the complete event — this exact
backup → wipe → restore → keep-playing cycle has been drill-tested live.

## Project status

The local event is working software: the full lifecycle (build → provision →
run → pause → backup → wipe → restore) has been exercised against the real
stack, and a scripted walkthrough solved all 80 questions end-to-end with
findings and points landing in IRIS and CTFd. Before the late-October event,
the remaining work is tracked in `docs/handoff/NEXT.md`:

- AWS deployment option (AMI, cloud fencing, teardown) — not yet built
- Ten-team capacity rehearsal on the actual event hardware
- A beginner rehearsal to validate the 4–5 hour duration with real people
- Final offline release bundle, operator freeze, and dress rehearsal

## Repository map

| Path | What it is |
|---|---|
| `participants/` | Participant worksheets and handover notes |
| `facilitator/` | Operator runbook, solutions, coaching, AAR guides |
| `expanded/` | Scenario authoring and content tooling |
| `ridge/` | The event platform: state core, deployment, CLI |
| `deployment/` | Container builds, compose files, example profiles |
| `docs/` | Architecture, operations, and planning documents |
| `docs/handoff/` | Build records and task cards from the development effort |
| `tests/` | Automated test suite (`python -m unittest discover -s tests`) |
| `app/`, `admin/`, root `Dockerfile` | Retired rehearsal portal, kept only as a test fixture — not part of the event |

All scenario content and answers are public by design (large evidence files
via Git LFS). Credentials, rosters, runtime directories and backups are
private and must never be committed.
