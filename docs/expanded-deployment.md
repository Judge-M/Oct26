# Offline deployment candidate

Check the current host using [Build first](handoff/BUILD-FIRST.md). Old reports
about a missing Docker/WSL/Java environment describe a previous preparation lane,
not a requirement or a diagnosis of this computer. Candidate versions are in
`deployment/expanded/versions.json`; pin final runtime images to immutable digests.

## Prepare and transfer

On a connected Linux preparation host, obtain IRIS v2.4.20, CTFd 3.7.7, the
official Wazuh Docker v4.9.2 single-node deployment, and Guacamole 1.5.5. Retain
licenses, complete configurations and source commit IDs. Build the three supplied
Dockerfiles from the repository root. Record source commit, image identity,
architecture, base digest and build log. Save every image/dependency to the
artifact store and transfer it before disconnecting the exercise network.

The IRIS extension uses its pinned ORM to commit task/comment changes and a unique
receipt atomically. Stock REST creation plus a separate receipt would not provide
that transaction. The CTFd OSS plugin likewise commits an Award and receipt
together; it supplies a dedicated coached-question interface, without stock
challenges or paid features. Runtime compatibility still requires testing against
the actual applications.

Source contracts inspected: [IRIS tasks](https://github.com/dfir-iris/iris-web/blob/v2.4.20/source/app/blueprints/case/case_tasks_routes.py),
[CTFd models](https://github.com/CTFd/CTFd/blob/3.7.7/CTFd/models/__init__.py), and
[CTFd plugin mechanism](https://docs.ctfd.io/docs/plugins/).

## Central services once per run

1. Create an isolated Docker network for integration-facing services and a
   separate network routed to desktop VNC ports. Set their runtime names. Never
   publish integration port 8091 to participant devices.
2. Load the built images. Set `IRIS_IMAGE`, `CTFD_IMAGE` and `RIDGE_IMAGE` to their
   validated immutable identities. Prepare the required private environment files.
3. Configure local authentication. Set CTFd to team mode and disable open
   registration. Create participant users inside the configured teams. Create an
   IRIS exercise case, read-only team users and a separate service user. Resolve
   actual open/closed task status IDs; never assume numeric status values.
4. Start root Compose for IRIS/CTFd. After the IRIS migration, run
   `flask silent-ridge-init` inside its app container once to create the receipt
   table. The CTFd plugin creates its credit table at load.
5. Install the transferred official Wazuh single-node stack with all required
   certificates/configuration and locally loaded images. Make its indexer
   reachable only through the local service network. Trust the local CA in the
   integration image, including via `SSL_CERT_FILE` if needed; do not disable TLS
   verification. Give the integration a writer restricted to `silent-ridge-*`;
   give participants read-only access to that historical index.
6. Index the initial JSONL with `ridge.evidence_release.index`. Create the
   `silent-ridge-*` data view using `timestamp`. Use the scenario's absolute UTC
   range. Participant agent installation is not part of the exercise.
7. Edit `expanded/config.json` with the actual identity mapping. Regenerate the
   authored content with `python expanded/author.py`; `expanded/tickets.json` is
   generated, not committed, and `ridge.cli init`/`migrate` require it. Initialize
   the core database on local storage. UID 10001 needs write access. Keep the database
   off NFS and participant shares.
8. Supply distinct IRIS and CTFd bridge secret files to their corresponding apps
   and the integration stack. Configure private release vault, published evidence
   and indexer paths. Add expected `iris_login` and `ctfd_name` values to every
   team mapping. Run `ridge.cli provision --operator EXCON-A` with the deployment
   environment to perform preflight and explicitly enable delivery. Start the
   integration Compose file. Initial tickets become
   claimable only after remote creation is acknowledged.
9. Start the Guacamole Compose file. Perform the end-to-end rehearsal below.

The Compose candidates use `pull_policy: never`. No runtime pip/apt, external
authentication, CDN, symbols or data downloads are allowed. Desktop accounts
receive no service secrets or target-write permissions. The supplied deployment
has not yet been run; the Wazuh stack and its dependency configuration must be
included from the pinned upstream artifact.

## Guacamole and explicit sharing

Generate the official PostgreSQL schema with the pinned Guacamole container's
`/opt/guacamole/bin/initdb.sh --postgresql`. Save it in a private initialization
directory. Generate a second provisioning SQL file:

```text
python deployment/expanded/guacamole.py expanded/config.json PRIVATE-CREDENTIALS.json PRIVATE-PROVISION.sql
```

The private input contains `teams: {team-id: {username, password}}` and
`desktops: {desktop-id: {password}}`. Use generated high-entropy login passwords
and per-desktop VNC passwords. SQL contains VNC passwords and must stay private.
Rotate/remove Guacamole's upstream default administrator account.

One persistent Xfce display runs per VM, served by TigerVNC. Every connection to
that team desktop sees the same keyboard, pointer and windows. `shared: true`
permits the configured simultaneous connection count; `shared: false` sets both
database connection limits to one. See the [Guacamole connection-limit schema](https://guacamole.apache.org/doc/1.5.3/gug/jdbc-auth.html).
No assumption about independent RDP logins sharing a session is made.

Team and desktop lists are configurable. Normally assign one desktop per team.
Additional devices can open IRIS/CTFd directly while a teammate uses the desktop.
The mapping currently supports one shared IRIS login and one CTFd team ID per
team. Unique CTFd participant accounts can belong to the same team.

## Linux template

Use the [prepared desktop image](desktop-image.md) for the supplied content and
tools. It includes the native capture and prepared case, with per-team runtime
credentials supplied separately. The following installation outline is for
rebuilding a template; it is not required to assemble the published disk.

Prepare Ubuntu 24.04/Xfce and an offline dependency closure for Firefox, Thunar,
TigerVNC, dbus and Wireshark. Copy the verified Autopsy Linux installation and
Cutter AppImage to the paths expected by `desktop/install.sh`. The installer
fails if these or the offline packages are missing. Record exact Java/TSK/native
library versions after successfully opening a representative Autopsy case.

Supply `/etc/silent-ridge/vnc-password` in TigerVNC password-file format. Restrict
VM port 5901 to guacd at the firewall. Mount only released evidence at `/evidence`
read-only. Give each team separate writable Cases, Workspace and Scratch folders.
Copy a closed prepared case into each team's Cases directory. Never share an
ordinary writable Autopsy case database. KAPE and Volatility are not installed.

This script configures an existing guest; it does not create a bootable VM image.
Export the validated guest using the selected hypervisor to the artifact store.
Final hypervisor, vCPU, memory and storage allocations require measurements.

## Container desktop (alternative to the Linux template)

The Docker-only alternative replaces the per-team VM with a container that
exposes VNC on the external `desktop` network, which `guacd` already reaches at
`hostname:5901`. See [container team desktop](docker-desktop.md) for the image
contract, `compose.desktops.yaml` usage, capacity guidance and offline packaging.
It removes QCOW2/`qemu-img`/Hyper-V/VirtualBox/cloud-init/AWS-AMI from the
critical path. The Linux template above and the
[prepared desktop image](desktop-image.md) remain the fallback. Nothing on this
path has been built or run.

## End-to-end acceptance

With Internet disconnected: log into every desktop; open each tool and the
disk/log/memory case; solve a question and verify one point plus one IRIS finding;
race claims; relinquish and resume; interrupt services after remote commits;
restart and check receipts; finish a ticket and inspect shared history/follow-up
evidence; export and reset. Test allowed sharing and exclusive mode. Attempt
unrelated direct question URLs and stock CTFd APIs. These steps remain unexecuted.
