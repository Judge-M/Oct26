#!/usr/bin/env bash
# Container entrypoint for the Silent Ridge per-team desktop.
# Credentials and organizer addresses are injected at runtime; none are baked in.
set -euo pipefail

VNC_PASSWORD_FILE="${VNC_PASSWORD_FILE:-/etc/silent-ridge/vnc-password}"
ENDPOINTS_FILE="${ENDPOINTS_FILE:-/etc/silent-ridge/endpoints.json}"
VNC_SECRET=/run/secrets/vnc_password
VNC_DISPLAY=:1

log() { printf 'silent-ridge-entrypoint: %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

[ "$(id -u)" = 0 ] || die 'entrypoint must start as root to read the VNC secret'

# Fail fast: the desktop stays unusable until a password secret is supplied.
[ -f "$VNC_SECRET" ] || die "VNC password secret $VNC_SECRET is absent; refusing to start"

install -d -m 755 /etc/silent-ridge
[ "$VNC_SECRET" != "$VNC_PASSWORD_FILE" ] || die 'VNC password output must differ from the read-only secret'
# The secret contains a plaintext password; TigerVNC requires its encoded file.
[ "$(wc -c < "$VNC_SECRET")" -ge 8 ] || die 'VNC secret must contain at least eight bytes'
umask 077
tigervncpasswd -f < "$VNC_SECRET" > "$VNC_PASSWORD_FILE"
chown participant:participant "$VNC_PASSWORD_FILE"

# Generate endpoints.json once, from the runtime organizer service addresses.
if [ ! -f "$ENDPOINTS_FILE" ]; then
  python3 - "$ENDPOINTS_FILE" <<'PY'
import json, os, sys
mapping = (('iris', 'IRIS_URL'), ('ctfd', 'CTFD_URL'), ('wazuh', 'WAZUH_URL'))
endpoints = {name: os.environ[env] for name, env in mapping if os.environ.get(env)}
with open(sys.argv[1], 'w', encoding='utf-8') as handle:
    json.dump(endpoints, handle, indent=2, sort_keys=True)
    handle.write('\n')
PY
  chown participant:participant "$ENDPOINTS_FILE"
fi

# Verify and seed the published case before making the desktop reachable.
python3 /opt/silent-ridge/seed-case.py /opt/silent-ridge/prepared-case /home/participant/Cases
chown -R participant:participant /home/participant/Cases

install -d -m 700 -o participant -g participant /run/user/1000

VNC_PID=
cleanup() {
  if [ -n "$VNC_PID" ] && kill -0 "$VNC_PID" 2>/dev/null; then
    kill "$VNC_PID" 2>/dev/null || true
    wait "$VNC_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT TERM INT

# A container restart reuses the writable layer; stale X locks from the
# previous run make Xtigervnc refuse display :1 and crash-loop the desktop.
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

runuser -u participant -- env HOME=/home/participant DISPLAY="$VNC_DISPLAY" XDG_RUNTIME_DIR=/run/user/1000 \
  Xtigervnc :1 -geometry 1440x900 -depth 24 -SecurityTypes VncAuth \
    -PasswordFile "$VNC_PASSWORD_FILE" -AlwaysShared -localhost no &
VNC_PID=$!

for _ in $(seq 1 50); do
  [ -S /tmp/.X11-unix/X1 ] && break
  sleep 0.2
done
[ -S /tmp/.X11-unix/X1 ] || die 'Xtigervnc did not create /tmp/.X11-unix/X1'

# Hand the session to participant under dbus; tini reaps the remaining children.
log 'starting Xfce session on :1'
trap - EXIT TERM INT
exec runuser -u participant -- env HOME=/home/participant DISPLAY="$VNC_DISPLAY" XDG_RUNTIME_DIR=/run/user/1000 \
  dbus-run-session -- startxfce4
