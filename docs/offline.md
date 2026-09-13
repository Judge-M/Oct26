# Reproducible offline deployment

The application image contains only the running app. Initialization, evidence
generation, configuration and release/reset require the controller source on the
host. An image tar alone is insufficient. The gateway image and nginx.conf are also
required. Package a validated source commit and both running image identities;
moving upstream tags are not the identity of an archived event.

## Prepare on a connected rehearsal host

Use Python 3.12, Docker Engine/Compose and Git. Commit the selected config.json and
source before packaging (a private branch is suitable for event-specific changes).
Run the tests, initialize a rehearsal run, build/start the services, and run the
container boundary and smoke checks. Record the test outputs in the private event
validation record. Then, from the repository root:

```text
python -m unittest discover -s tests -v
python scripts/exercise.py init
docker compose pull gateway
docker compose build
docker compose up -d --wait
python scripts/check_container.py
python scripts/smoke.py
python scripts/offline.py pack build/offline
docker compose down
```

Use a clean rehearsal checkout; init refuses an existing runtime and smoke writes
a rehearsal comment. Packaging captures the source commit with git archive, config,
controller scripts, handout templates, Dockerfile, Compose, nginx.conf, and tests.
It saves both **running** image IDs with `docker image save` into images.tar, records
RepoDigests where present, OS/architecture, host Python/SQLite and engine/Compose versions, and
creates a compose.offline.json override with immutable-ID-derived local tags.
The locally built app may have no RepoDigest; its full sha256 image ID is recorded.
Do not rebuild on the offline host: that could resolve a different base image.

SHA256SUMS.json covers every packaged file including images.tar, source.zip, the
unpacked controller tree and gateway config. Record the printed SHA-256 of that
manifest through a trusted channel outside the package. Transfer the entire
build/offline directory privately: the source contains facilitator answers but
excludes runtime, credentials, .env, participant work and exports. Also provide
offline installers for the recorded Python version and compatible Docker/Compose
and any forensic tools. Docker/WSL installation and licensing must be completed
before air-gapping; the package does not install the container engine or OS features.

## Restore on a clean offline host

Use the recorded OS/architecture (Linux containers) and matching Python/SQLite
runtime for byte-reproducible evidence. In PowerShell, compare
`(Get-FileHash .\SHA256SUMS.json -Algorithm SHA256).Hash` with the trusted manifest
hash; on Linux use `sha256sum SHA256SUMS.json`. Then from the package directory:

```text
python source/scripts/offline.py verify .
python source/scripts/offline.py load .
python -c "import shutil; shutil.copytree('source', '../silent-ridge-run')"
cd ../silent-ridge-run
python scripts/exercise.py init
python scripts/exercise.py verify
docker compose -f compose.yaml -f compose.offline.json up -d --no-build --pull never --wait
python scripts/check_container.py
python scripts/smoke.py
docker compose -f compose.yaml -f compose.offline.json down
python scripts/exercise.py reset --stopped
docker compose -f compose.yaml -f compose.offline.json up -d --no-build --pull never --wait
```

Keep the transferred package unchanged; restore into the separate new directory shown
above. copytree refuses an existing destination. Load verifies the package, performs `docker image load`, and compares full image IDs
and platforms before startup. Both services use restored tags and prohibit pulls;
--no-build prevents the app's build stanza from triggering a base-image download.
Only host Python and loaded images are used for initialization/startup. Do not
discard source/scripts, source/config.json or source/deployment/nginx.conf.
Use explicit Compose files on subsequent up/down commands too. The project name
remains silent-ridge, so boundary/smoke scripts inspect the correct services.

The first smoke is a rehearsal mutation. Stop/reset afterward as shown for clean
participant tickets and fresh credentials. Distribute only portal access and
rendered initial handouts. To retain an existing run instead, keep a separate private
full-runtime backup after stopping services, restore its permissions and run verify;
the deploy package itself intentionally contains no prior run or login credentials.

## Validation limits

CI exercises image save/load and startup from the packaged source with builds and
pulls prohibited. A clean physical host with no cached images, offline installer
availability, WSL/virtualization readiness, lab routing, Jira connectivity and a timed
human rehearsal still require validation on event equipment. Keep actual image IDs,
package checksum, commands and outcomes with the event record. Never label a merely
created package as a successful clean-host rehearsal.
