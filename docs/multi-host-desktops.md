# Multi-host Guacamole desktop workers

The central event services remain on one primary host. Optional Docker workers
run only participant desktop containers. Guacamole still presents one URL and
one set of team connections; participants do not know which host runs a
desktop.

This is an opt-in extension of the single-host deployment. Profiles without a
`worker` field continue to run every desktop on the primary host.

## Trust and network boundary

- The primary host controls registration, credentials, Guacamole, and the
  exercise state.
- A worker runs the reviewed `silent-ridge-desktop` image and mounts a staged,
  read-only copy of the prepared case and evidence.
- The primary controls workers through a named Docker context using SSH public
  keys. Do not expose an unauthenticated Docker TCP socket.
- A remote desktop publishes one VNC port on the worker LAN address. The worker
  firewall must allow that port **only from the primary host**. Participant
  devices never connect to VNC directly.
- Keep SSH/Docker context names and worker filesystem paths in private
  `RUNTIME/local.json`; do not commit them.

## Capacity planning

Every dynamic team receives three desktops. A ten-team pool therefore has 30
slots even though only registered teams are started. The validator checks all
30 slots and applies 20% memory headroom on each host.

For two 64 GiB / 20-thread machines with roughly 475 GiB of usable disk each,
a conservative starting placement is 11 slots on the primary and 19 on the
worker. The primary also carries CTFd, IRIS, Wazuh, Guacamole, and the
integration services. With the sample reservations below, 12 local slots would
require 490 GiB on the primary and is therefore rejected by the validator.

Declare each remote worker's usable capacity under `capacity.workers`:

```json
"capacity": {
  "host": {"vcpus": 20, "memory_mib": 65536, "disk_gib": 475},
  "central": {"vcpus": 6, "memory_mib": 8192, "disk_gib": 250},
  "desktop": {"vcpus": 1, "memory_mib": 2048, "disk_gib": 20},
  "workers": {
    "worker-02": {"vcpus": 20, "memory_mib": 65536, "disk_gib": 475}
  }
}
```

## Profile placement

Local slots need no additional fields. Remote slots name a worker and use a
unique LAN endpoint. Reusing an address and port is rejected.

```json
{"name": "desktop-slot11", "address": "172.18.0.21",
 "shared": true, "max_connections": 5},
{"name": "desktop-slot12", "address": "192.168.1.3", "vnc_port": 5901,
 "worker": "worker-02", "shared": true, "max_connections": 5},
{"name": "desktop-slot13", "address": "192.168.1.3", "vnc_port": 5902,
 "worker": "worker-02", "shared": true, "max_connections": 5}
```

The dynamic allocator retains deterministic slot order. Put the desired mix in
the profile before creating the runtime; do not change placement underneath an
active registration database.

## Private primary-host configuration

Add every non-local worker referenced by the profile to `RUNTIME/local.json`:

```json
"desktop_workers": {
  "worker-02": {
    "docker_context": "ridge-worker-02",
    "vnc_password_dir": "C:/SilentRidge/runtime/secrets/vnc",
    "assets": {
      "case_template": "C:/SilentRidge/Oct26/evidence/prepared-case",
      "evidence_public": "C:/SilentRidge/Oct26/evidence/public",
      "originals": "C:/SilentRidge/Oct26/evidence/originals"
    }
  }
}
```

These are paths as seen by the worker's Docker daemon. Stage the same reviewed
evidence and prepared case at those paths. Copy all pre-generated VNC secret
files to `vnc_password_dir` over the protected management channel; they are not
participant credentials and must not be placed in Git.

## Worker preparation

1. Give the worker a stable DHCP reservation and record its exact LAN address.
2. Install Docker Engine or Docker Desktop with Linux containers. Start it and
   verify `docker run --rm hello-world` locally.
3. Install and start OpenSSH. Use key authentication for the event controller.
4. Restrict inbound SSH to the primary host.
5. Restrict the assigned VNC range to the primary host. For slots mapped to
   ports 5901 through 5919 on a Windows worker:

   ```powershell
   New-NetFirewallRule -DisplayName "Silent Ridge VNC from primary" `
     -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5901-5919 `
     -RemoteAddress 192.168.1.200 -Profile Private
   ```

6. Stage the source/release assets and private VNC directory at the paths in
   `local.json`.
7. Transfer the reviewed desktop image; do not independently rebuild it:

   ```text
   docker image save silent-ridge-desktop:dev -o RUNTIME/desktop-image.tar
   docker --context ridge-worker-02 image load -i RUNTIME/desktop-image.tar
   ```

8. Create the SSH-backed Docker context on the primary and verify it:

   ```text
   docker context create ridge-worker-02 --docker host=ssh://WORKER_USER@192.168.1.3
   docker --context ridge-worker-02 info
   ```

The lifecycle then renders a private worker environment and Compose override.
Registration groups the assigned three services by worker, waits for every
container to become healthy, and only then publishes Guacamole access. A failed
worker start requeues the registration and stops any services started for that
attempt.

## Acceptance checks

Before opening registration:

```text
python -m ridge.deploy doctor --profile PROFILE --runtime RUNTIME
python -m ridge.deploy up --profile PROFILE --runtime RUNTIME
python -m ridge.deploy status --profile PROFILE --runtime RUNTIME
docker --context ridge-worker-02 ps
```

Register one test team whose allocation crosses the host boundary. Confirm:

- all three connections appear in its Guacamole handout;
- each desktop opens and accepts keyboard/mouse input;
- `/evidence`, `/originals`, and the prepared Autopsy case are present;
- Guacamole can reach the worker while a participant laptop cannot connect
  directly to the worker VNC ports;
- a worker outage leaves registration retryable rather than issuing a partial
  handout.

## Data-protection boundary

Normal `down` stops remote worker projects. `down --volumes` is intentionally
refused when remote workers are configured because recovery schema 1 does not
yet archive worker-local named volumes. Preserve worker volumes and export any
participant work before retiring a worker. Central databases, scores, evidence,
credentials, and registration state remain covered by the existing verified
backup.

