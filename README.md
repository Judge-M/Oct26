# Operation Silent Ridge

A cooperative incident-response CTF for **ten teams / thirty participants**.
Teams claim IRIS tickets, investigate with Autopsy, Wireshark, Cutter and Wazuh,
and answer coached CTFd questions. Accepted findings and equal-value points
persist globally across ownership changes.

**Not event-ready.** Published native evidence, the prepared Autopsy case and VM
desktop exist. The transactional core has tests and an actual CTFd adapter smoke.
The consolidated deployment source still needs the live two-team integration,
full local lifecycle, recovery, AWS, offline-release and ten-team acceptance gates.
A passing unit test is not proof that an image has been built or a service started.

## Start here

- [Agent instructions](AGENTS.md)
- [Build first, then run](docs/handoff/BUILD-FIRST.md)
- [Next bounded implementation tasks](docs/handoff/NEXT.md)
- [Copyable starter prompt](docs/handoff/STARTER-PROMPT.md)
- [Disposition of old PRs 14–20](docs/handoff/CONSOLIDATION.md)

## Build and check

```text
python -m ridge.deploy doctor
python -m ridge.deploy build
python -m ridge.deploy verify-build
python -m unittest discover -s tests
```

Read the build guide first for Git LFS, case preparation and Docker prerequisites.
Builds download dependencies during preparation. Event-day offline setup and AWS
switching are still acceptance targets, not working commands. The current CLI
fails closed for unimplemented event lifecycle operations.

## Content and deployment

All fictional content and answers are public. Large event artifacts live in Git
LFS with manifests under `assets/`; credentials, real rosters and live backups stay
private. A fresh computer does not need the original workstation's event files.

The published Ubuntu VM remains available. An additional container desktop build
uses the same prepared case and evidence paths. Central services and desktops
must be built, configured and tested together before either path is event-ready.

- [Published desktop](docs/desktop-image.md)
- [Distribution and asset policy](docs/github-distribution.md)
- [Acceptance record](docs/expanded-validation.md)
- [Learning objectives](docs/learning-objectives.md)
- [Original task cards and acceptance contract](docs/handoff/EXECUTION.md)

Twenty tickets contain eighty questions. The 1,300 team-minute estimate is
unmeasured and does not establish four hours of learning for every team.
The old `app/` and `admin/` portal is retained only as a baseline test fixture.
