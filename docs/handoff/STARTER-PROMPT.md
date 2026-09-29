# Copy this prompt into your coding agent

```text
Work on Judge-M/Oct26 using the consolidated replacement PR/current main,
not the retired PR 14–20 branches. First read AGENTS.md, then
docs/handoff/CONSOLIDATION.md, BUILD-FIRST.md and NEXT.md.

Implement task N1 only. Our goal is a complete portable CTF for ten teams /
thirty participants, with all fictional content and reproducible build inputs
on GitHub. The immediate milestone is a real two-team local deployment.

Inspect this computer's actual capabilities. Do not assume a missing Docker
engine or hypervisor from old notes. Check the Docker daemon as well as its CLI.
Fetch the required Git LFS artifacts, verify their checksums, and ACTUALLY BUILD
the images using the documented commands. Wait for successful builds and run
verify-build before starting any program/container from those images. A syntax
check, image URL, Dockerfile or passing unit test is not a completed build.
If building fails, fix that first. Never bypass checks or replace code with mocks.

Use the existing ridge/deploy package and profile schema. Wire real provisioning
and discover native IDs; do not invent a second provider or deployment module.
Keep initialization paused and retries idempotent. Use generated private secrets;
do not commit credentials, real rosters or live state. Retain existing published
memory, case and VM artifacts and preserve their facts.

Perform routine source changes, builds and isolated tests without asking me at
every step. If a truly required permission, machine capability or credential is
missing, show the exact command/error and the minimum missing input. Do not
install a new host stack, spend on AWS, expose public ports or delete existing
resources without authorization. Do not skip to later waves while blocked.

Before ending, commit the focused work and record exact build commands, exit
codes, image IDs, tests, sanitized evidence and unresolved acceptance gates.
Clearly distinguish source implemented, image built, service running, live
acceptance passed and event-ready. Stop after N1 with the next task identified;
do not merge automatically. If N1 already has verified evidence on this checkout,
report that evidence and take the next single unaccepted task in NEXT.md instead.
```
