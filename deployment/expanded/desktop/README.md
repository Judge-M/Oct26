# Container desktop build

Follow [Build first](../../../../docs/handoff/BUILD-FIRST.md) from the repository root.
The underlying build is `docker build -f deployment/expanded/desktop/Dockerfile
-t silent-ridge-desktop:dev .`; use `python -m ridge.deploy build --component desktop`
to also record source and image identities. Do not run until `verify-build` passes.

All four downloaded tool archives have SHA-256 pins. Autopsy uses Java 17 and
Sleuth Kit builds Java targets sequentially. This online preparation step is not
the complete offline release bundle.

Mount a verified case template read-only at `/opt/silent-ridge/prepared-case`.
Startup verifies it and seeds `/home/participant/Cases/WS17` exactly once. Existing
participant work is never overwritten. Mount each team's Cases/Workspace/Scratch
on separate persistent volumes, and mount `/evidence` and `/originals` read-only.

Supply a plaintext VNC password as a Compose secret at `/run/secrets/vnc_password`.
The entrypoint encodes it into `/etc/silent-ridge/vnc-password`; input and output
must differ. VNC is private to guacd and never host-published. Do not use
`docker run --secret` (not a docker run option); use Compose or a read-only bind.

Run `bash tests/desktop_container_smoke.sh` on a disposable Linux Docker worker.
Full Guacamole login, Autopsy case search and multi-team acceptance remain gates.
