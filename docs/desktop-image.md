# Prepared team desktop

> **Fallback notice.** The container-desktop path in
> [docker-desktop.md](docker-desktop.md) is now the proposed primary desktop
> design. This VM/QCOW2 document is retained as the fallback; its content is
> unchanged.

The Ubuntu 24.04 amd64 desktop contains Autopsy 4.22.0, SleuthKit 4.13.0,
Cutter 2.5.0, Firefox 140.16.0esr, Wireshark, XFCE and TigerVNC. It includes
the closed WS17 version-two case, released evidence and original native Windows
capture. Each team needs its own writable disk/case copy.

## Assemble

After cloning with Git LFS installed, run `git lfs pull`, then:

```text
python -m ridge.desktop_image --destination work/silent-ridge-desktop.qcow2
```

The manifest `assets/desktop-v1.json` lists ordered parts, per-part SHA-256 and
the complete disk checksum. Assembly streams data and publishes the disk only
after all checks pass. An existing destination is never overwritten. Allow
space for both downloaded parts and the assembled disk. The virtual disk is
30 GiB; its runtime host must also accommodate team changes and case exports.

The disk uses QCOW2 for QEMU/KVM. Hyper-V needs conversion, for example on a
preparation host with QEMU installed:

```sh
qemu-img convert -f qcow2 -O vhdx silent-ridge-desktop.qcow2 silent-ridge-desktop.vhdx
```

Hyper-V boot and AWS import are not yet validated. The QCOW2 file is not an
AWS AMI. Cloud import, networking, Guacamole registration, per-team cloning and
teardown still require deployment integration; this command assembles content.

## Runtime configuration

The image has no published VNC password or organizer service credentials.
Cloud-init accepts NoCloud or EC2 metadata. Supply a private administrative SSH
key through deployment metadata when administration is needed. Temporary builder
access is locked and its home and authorized keys removed.

Provision a unique TigerVNC password file at
`/etc/silent-ridge/vnc-password`, readable by `participant` and not other users.
Use `tigervncpasswd` during private provisioning; do not commit that file.
Create `/etc/silent-ridge/endpoints.json` with `iris`, `ctfd` and `wazuh` HTTP(S)
URLs, then start `silent-ridge-desktop.service`. Until the password file exists,
the service deliberately stays stopped. Restrict TCP 5901 to the Guacamole
gateway network; it must not be exposed directly to the Internet.

Evidence is mounted read-only at `/evidence` and `/originals`. Open
`/home/participant/Cases/WS17/WS17.aut` in Autopsy. Its source paths resolve
without new ingest. The prepared original case is also available at
`/opt/silent-ridge/prepared-case/WS17`. Participant work belongs in the writable
case copy or `Workspace`; export it privately before discarding a team disk.

## Build and validation record

Source image, tool checksums, installed package versions and validation results
are recorded beside the desktop manifest. The source Ubuntu Azure cloud disk
was adapted to Ubuntu's generic kernel and NoCloud/EC2 metadata. The Azure
agent is disabled. The generic kernel boot was verified before sealing.

`deployment/expanded/desktop/configure-image.sh` installs the desktop launchers
and service after tools are staged. `seal-image.sh` is for the disposable guest
only: it removes temporary build access, test profiles, host SSH keys and cloud
state, resets machine identity, and shuts down. Free filesystem blocks are then
zeroed offline before compressed export. Never run sealing against a live event
or a personal workstation.

The GUI opened the prepared Autopsy case and its 90-document keyword index;
`BriefSync` returned six matches. Cutter analyzed the included training binary
and found 11 functions and 16 strings. Firefox and Wireshark also launched in
the shared desktop. These checks do not replace a 10-team capacity rehearsal
or full IRIS/CTFd/Wazuh/Guacamole acceptance.
