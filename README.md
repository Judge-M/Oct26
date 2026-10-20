# Operation Silent Ridge

A cooperative, defensive incident-response exercise for **up to ten teams of five**.
Participants investigate a fictional breach using real forensics and detection
tools — Autopsy, Wireshark, Cutter and Wazuh — coordinated through a shared
IRIS case, with questions and scoring in CTFd. Teams claim investigation
tickets, submit findings, and earn equal-value points that persist even when a
ticket changes hands. Everything in the scenario is fictional; the evidence,
the tools, and the teamwork are real.

This repository contains the full event: the authored scenario and evidence,
the tooling that builds and runs it, the participant materials, and the
facilitator guides.

## Start here

### Event organizer: fastest supported path

1. **Prepare the event network first.** Give the event host a stable LAN
   address. For public HTTPS mode, configure the event network's DHCP to hand
   out the event DNS service, with these names resolving to the event host:

   ```text
   ctfd.cyberexperts.org   192.168.1.200
   iris.cyberexperts.org   192.168.1.200
   guac.cyberexperts.org   192.168.1.200
   wazuh.cyberexperts.org  192.168.1.200
   ```

   Use an event-owned router/access point when possible. Do not run a second
   DHCP server on a shared venue network. If the venue DNS/DHCP cannot be
   changed, use the hosts-file onboarding fallback described in
   [public HTTPS certificates](docs/external-tls.md).
2. **Install the offline release bundle** from the
   [latest release](https://github.com/Judge-M/Oct26/releases). This is the
   event-day path; source builds are for a connected preparation machine.
3. **Configure the private runtime.** Copy the example runtime configuration,
   set the host address and asset paths, and follow the
   [event-day command sheet](docs/event-day-commands.md). If using the trusted
   wildcard certificate, configure it before `up` using
   [public HTTPS certificates](docs/external-tls.md). Never commit the private
   key or runtime secrets.
4. **Provision and start the event.** For fixed teams, run `up --teams N`.
   For self-service registration, use `deployment/profiles/example-dynamic.json`
   and do not pass `--teams`:

   ```bash
   python -m ridge.deploy doctor --profile PROFILE --runtime RUNTIME
   python -m ridge.deploy up --profile PROFILE --runtime RUNTIME
   python -m ridge.deploy status --profile PROFILE --runtime RUNTIME
   python -m ridge.deploy start --profile PROFILE --runtime RUNTIME
   python -m ridge.deploy registration-open --profile PROFILE --runtime RUNTIME
   ```

5. **Put the registration page on the screen.** In trusted public HTTPS mode,
   open `https://ctfd.cyberexperts.org/silent-ridge/register` (or the CTFd
   hostname configured in `local.json`). If you want a friendlier `event.`
   alias, add it to the local DNS records and TLS hostnames before `up`. In
   generated-CA mode, use
   `https://HOST:8083/silent-ridge/register` after distributing the participant
   CA. The page contains the initial brief and gives each registered team a
   bookmarkable handout with five personal CTFd seats, its service credentials,
   and the names of its three isolated desktop connections. Registration starts
   closed; give captains the enrollment code from
   `RUNTIME/secrets/registration-enrollment-code`, then open the window with the
   command above.

### Participant: how to begin

Connect to the event network, open the registration URL provided by the
organizer, read the initial brief, and register one team. Bookmark the private
retrieval link shown after registration. Use the three Guacamole desktop links
for GUI-only tools; use the IRIS, CTFd, and Wazuh links directly in browser tabs.
No software should be installed on participant laptops in the containerized
desktop path.

## I want to run the event — where do I start?

You do not need to know anything about how this project is built. You need
one capable machine, Docker, and about half a day of preparation. Follow
these steps in order; each one tells you when it is done.

1. **Check your machine.** 32 GB RAM (64 GB comfortable), 16 CPU cores,
   100 GB free SSD, Docker installed and running. Details and the
   measurements behind these numbers:
   [What you need to host it locally](#what-you-need-to-host-it-locally).
2. **Get the software onto that machine.** Download the offline bundle
   from the
   [latest release](https://github.com/Judge-M/Oct26/releases) and install
   it — no internet needed afterwards, and no build step. This is the
   intended path for event day; the exact install commands are in the
   [command sheet](docs/event-day-commands.md). (Building from source is a
   developer path — see [Quick start](#quick-start).)
3. **Bring the event up.** Follow
   **[docs/event-day-commands.md](docs/event-day-commands.md)** — it is the
   complete cold-machine → running-event → teardown checklist with exact
   commands, written to be followed literally. It covers install, the
   pre-flight check (`doctor`), starting the stack with your team count
   (`up --teams N`), verifying it is ready, and what to hand out.
4. **Brief the participants.** Project
   **[docs/event-day-deck/event-day-deck.pdf](docs/event-day-deck/event-day-deck.pdf)**
   — 13 slides that tell the story and walk participants through every
   login, click by click, assuming zero prior knowledge. It is a plain PDF,
   so it projects anywhere with no software to install. Hand each team its
   account sheet (the command sheet says where those files are).
5. **Run the day.** The command sheet covers starting the clock, messaging
   all teams, pausing, and recovering a stuck team. The
   [operator runbook](docs/runbook.md) is the one-page symptom → action
   reference while the event is live.
6. **Afterwards.** One command makes a verified backup; one more tears
   down. See [Backup, restore, teardown](#backup-restore-teardown).

If something breaks, the command sheet links the troubleshooting table, and
the participant deck has a "what to try before raising a hand" slide.

## What participants experience

Each five-person team receives three isolated, container-hosted Linux desktops
through Guacamole—Forensics A, Forensics B, and Analysis. Everything else
happens in the participants' own browser tabs; nothing is installed on their
laptops.
Teams:

1. Claim up to three investigation tickets in IRIS (the shared incident case).
2. Investigate with the desktop tools: disk images in Autopsy, network
   captures in Wireshark, a suspicious binary in Cutter, logs in Wazuh.
3. Answer the ticket's questions in CTFd. An unassisted correct answer scores
   four points and posts the finding back into the shared IRIS case
   automatically. Help levels 1 and 2 are free; unlocking the explicit
   walkthrough applies an exact 75% cost, leaving one point for that question.
   Every team's work still helps everyone else's picture of the incident.
4. Every team works through all 20 tickets and 80 questions. Later phases unlock
   only when that team completes the required earlier phase.

The event is designed for a 4–5 hour day including orientation, a break, and
a facilitated after-action review.

## What you need to host it locally

One machine runs the whole event. Sized from live measurement of the real
stack, not guesswork:

- **32 GB RAM minimum; 64 GB is comfortable.** Measured on the running stack:
  central services use ~6 GiB; each team desktop idles at ~150 MiB and peaks
  at ~2 GiB with the Autopsy case open and its text index loaded. Thirty desktop
  containers are available for ten teams; actual simultaneous loaded-tool use,
  central services, and the host OS must remain inside the verified host budget.
  Desktop containers carry a 4 GB memory *limit*, but a limit reserves
  nothing — the host only commits what is actually touched.
- **16 CPU cores recommended**, gigabit LAN for participant browsers
- **100 GB free NVMe SSD** — measured: ~19 GB of container images, ~14 GB for
  the offline bundle, plus build cache and runtime growth
- **Docker** (Docker Desktop on Windows, or Docker Engine on Linux)
- **Python 3.11+** and **Git with Git LFS** for the build host

A two-team pilot runs comfortably on 16 GB RAM (measured: ~8.4 GiB for the
whole stack with two desktops, one under Autopsy load).

## Quick start

**Hosting the event? Use the offline bundle** from the
[releases page](https://github.com/Judge-M/Oct26/releases) and follow the
[command sheet](docs/event-day-commands.md) — it covers install, content
assets, and bring-up with exact commands.

Building from source is the **online preparation/developer path**. It may
download base images, operating-system packages, and pinned tool archives even
when Docker already has the base image cached. Cache preference does not make a
source build suitable for an air-gapped event host; the complete release bundle
above is the sole supported offline event path. Note that
`build --component all` produces only the container images — the content
assets (evidence tree, Autopsy case template, Wazuh config, release vault)
come from the release bundle or the content pipeline documented in
[`docs/handoff/BUILD-FIRST.md`](docs/handoff/BUILD-FIRST.md). To build
images:

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

Team count is a start-time switch, not a profile rewrite:
`up --teams N` (1–10) provisions N neutral teams (team-01…team-N, three
seats each) on N desktops no matter what the profile roster says. The
choice is recorded in the runtime and reused by every later command; use
a fresh runtime directory to change it. The profile's declared host
capacity is still checked against the requested count.

For the event-day self-service roster, copy
`deployment/profiles/example-dynamic.json` instead. Do not pass `--teams`.
After `start`, open registration and send teams to
`https://ctfd.cyberexperts.org/silent-ridge/register`.
The landing page contains the initial brief; each registration reserves five
seats and three GUI-only desktops, starts those three slots through the
host-side allocator, creates the CTFd/IRIS/Guacamole identities, and returns a
bookmarkable handout with all URLs, credentials, and exact Guacamole connection
names. The runtime registration
database is private and is not part of the repository.

`up` builds out the entire stack and stops at a verified, paused state —
nothing is visible to participants until you explicitly `start`. The `runtime`
directory is private: it holds the event's secrets, state, and the team
account inventories you hand out to participants. On Windows, `ridge.ps1`
wraps the same commands (`.\ridge.ps1 prepare / up / status / start ...`).

In the event's trusted public-TLS mode, participants use these port-443 names.
The event DNS maps them to the LAN address, and the reverse proxy routes each
name to its internal service:

| What | Where |
|---|---|
| Team desktops (Guacamole) | `https://guac.cyberexperts.org` |
| IRIS incident case | `https://iris.cyberexperts.org` |
| CTFd questions and score | `https://ctfd.cyberexperts.org` |
| Wazuh dashboard | `https://wazuh.cyberexperts.org` |

Fresh runtimes generate random facilitator, participant, database, and service
credentials. Retrieve them only from the private runtime or a team's private
registration handout; never commit, publish, or substitute memorable defaults.
Existing runtimes retain their generated credentials when upgraded. The
generated-CA/IP-and-port path remains an offline fallback; only that fallback
requires the participant trust steps in
[`docs/participant-ca-trust.md`](docs/participant-ca-trust.md).

## Running the event

On event day, the [presenter landing page](docs/presenter-landing.html) is
the single entry point on the presenter PC: deck, participant URLs, operator
docs, run-of-show, and runbook quick reference — one offline file.

The [event-day command sheet](docs/event-day-commands.md) is the
cold-machine → running-event → teardown checklist with exact commands.
The [participant briefing deck](docs/event-day-deck/event-day-deck.pdf)
(13 slides, PDF) is what you project at the start: it explains the
scenario and walks participants through setup click by click.
The [facilitator closing brief](docs/facilitator-closing-brief.md) is the
canonical ending used after T20. Completion automatically reveals the final
assessment and containment actions in CTFd and publishes the same assessment
to IRIS. The facilitator then plays or reads the outro once for the entire
room; participant-controlled media playback is intentionally unavailable.

```bash
python -m ridge.deploy pause   --profile ... --runtime ...   # pause the clock
python -m ridge.cli announce --operator EXCON --text "..."   # message all teams
python -m ridge.cli recover T03 --generation 1 --operator EXCON --reason "..."
```

Facilitator materials (solutions, coaching and AAR guides) live in
`facilitator/`; participant worksheets in `participants/`. The
[operator runbook](docs/runbook.md) is the one-page event-day reference with
recovery appendices; see `docs/expanded-operations.md` for the deeper guide.

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
findings and points landing in IRIS and CTFd. An offline drill release,
[`v0.9.0-drill`](https://github.com/Judge-M/Oct26/releases/tag/v0.9.0-drill),
packages every image and asset and has been cold-install-tested from the
release page alone (fresh download, hash-verified, all 13 images loaded). Its
notes carry the install steps and the honest certification gaps. Event-day
materials are ready: the operator command sheet
(`docs/event-day-commands.md`) and the participant briefing deck
(`docs/event-day-deck/`).

**Picking up development (human or agent): start at
[`docs/handoff/NEXT.md`](docs/handoff/NEXT.md)** — its "Current position"
section says what is done, what is in flight, and the single next action,
with links to receipts and evidence. Task cards live alongside it in
`docs/handoff/tasks/`.

Before the
late-October event, the remaining work is tracked in `docs/handoff/NEXT.md`:

- Ten-team capacity rehearsal on the actual event hardware
- Desktop image rebuild with the measured Autopsy heap cap, then the final
  event release, operator freeze, and dress rehearsal
- A beginner rehearsal to validate the 4–5 hour duration with real people
- AWS deployment option (AMI, cloud fencing, teardown) — deferred until the
  local release is proven

## Repository map

| Path | What it is |
|---|---|
| `participants/` | Participant worksheets and handover notes |
| `facilitator/` | Operator runbook, solutions, coaching, AAR guides |
| `expanded/` | Scenario authoring and content tooling |
| `ridge/` | The event platform: state core, deployment, CLI |
| `deployment/` | Container builds, compose files, example profiles |
| `docs/` | Architecture, operations, and planning documents |
| `docs/event-day-commands.md` | **Run the event**: cold-machine → teardown checklist |
| `docs/event-day-deck/` | **Brief participants**: 13-slide setup + story deck |
| `docs/presenter-landing.html` | **Event-day hub on the presenter PC**: deck + URLs + operator docs, offline |
| `docs/handoff/` | **Start here when picking up work**: `NEXT.md` (current position), receipts, evidence, and task cards |
| `tests/` | Automated test suite (`python -m unittest discover -s tests`) |
| `app/`, `admin/`, root `Dockerfile` | Retired rehearsal portal, kept only as a test fixture — not part of the event |

All scenario content and answers are public by design (large evidence files
via Git LFS). Credentials, rosters, runtime directories and backups are
private and must never be committed.

## License

Project-authored source code and documentation are licensed under the
[Apache License 2.0](LICENSE). Third-party components, container images,
evidence and assets retain their respective licenses and notices; see
[NOTICE](NOTICE).

## Room-wide narrative briefs

The [two-brief package](docs/handoff/audio-briefs/README.md) provides the approved
introduction and final assessment from Faye Maxwell, SOC supervisor for Operation
Silent Ridge. Both are room-wide facilitator cues: play the introduction once at
the beginning and the conclusion once during wrap-up after the final assessment is
visible. No participant page links to or plays the media. The package contains the
canonical scripts and production handoff; final outro audio or video still requires
production and listening acceptance.
