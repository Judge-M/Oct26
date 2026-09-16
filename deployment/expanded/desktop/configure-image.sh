#!/usr/bin/env bash
# Configure a prepared Ubuntu 24.04 guest. Runtime credentials are supplied later.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run inside the desktop build guest as root'; exit 1; }
test -x /opt/autopsy/bin/autopsy
test -f /opt/cutter/Cutter.AppImage
id participant >/dev/null 2>&1 || useradd --create-home --shell /bin/bash participant
install -d -o participant -g participant /home/participant/{Desktop,Cases,Workspace,Scratch}
install -d /etc/silent-ridge /opt/silent-ridge /originals
mkdir -p /evidence
if [[ -f /opt/firefox.tar.xz && ! -x /opt/firefox/firefox ]]; then
  tar -xJf /opt/firefox.tar.xz -C /opt
fi
ln -sfn /opt/firefox/firefox /usr/local/bin/firefox
chmod 755 /opt/cutter/Cutter.AppImage
ldconfig
for tool in startxfce4 Xtigervnc wireshark firefox thunar dbus-run-session; do command -v "$tool"; done
cat >/opt/silent-ridge/open-autopsy.sh <<'AUTOPSY'
#!/bin/bash
cd "$HOME"
export SOLR_LOGS_DIR="$HOME/.local/state/autopsy-solr/logs"
export SOLR_PID_DIR="$HOME/.local/state/autopsy-solr"
mkdir -p "$SOLR_LOGS_DIR" "$SOLR_PID_DIR"
exec /opt/autopsy/bin/autopsy -J--module-path=/usr/share/openjfx/lib \
  -J--add-modules=javafx.controls,javafx.swing "$@"
AUTOPSY
cat >/opt/silent-ridge/start-desktop.sh <<'DESKTOP'
#!/bin/bash
set -euo pipefail
Xtigervnc :1 -geometry 1440x900 -depth 24 -SecurityTypes VncAuth \
  -PasswordFile /etc/silent-ridge/vnc-password -AlwaysShared -localhost no &
vnc_pid=$!
trap 'kill "$vnc_pid" 2>/dev/null || true' EXIT
for attempt in {1..50}; do test -S /tmp/.X11-unix/X1 && break; sleep .2; done
dbus-run-session -- startxfce4
DESKTOP
cat >/opt/silent-ridge/open-service.py <<'PY'
#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys
config = Path('/etc/silent-ridge/endpoints.json')
if not config.exists():
    subprocess.run(['zenity', '--error', '--text=The organizer has not configured service addresses yet.'])
    raise SystemExit(1)
url = json.loads(config.read_text())[sys.argv[1]]
if not isinstance(url, str) or not url.startswith(('https://', 'http://')):
    raise SystemExit('Expected an HTTP or HTTPS service URL')
subprocess.run(['/usr/local/bin/firefox', url], check=True)
PY
chmod 755 /opt/silent-ridge/{open-autopsy.sh,start-desktop.sh,open-service.py}
cat >/etc/systemd/system/silent-ridge-desktop.service <<'UNIT'
[Unit]
Description=Shared Silent Ridge team desktop
After=network.target
ConditionPathExists=/etc/silent-ridge/vnc-password
[Service]
User=participant
Environment=HOME=/home/participant
Environment=DISPLAY=:1
ExecStart=/opt/silent-ridge/start-desktop.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
shortcut() {
  local title="$1" command="$2"
  cat >"/home/participant/Desktop/$title.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$title
Exec=$command
Terminal=false
EOF
}
shortcut 'Incident queue' '/opt/silent-ridge/open-service.py iris'
shortcut 'Questions and help' '/opt/silent-ridge/open-service.py ctfd'
shortcut 'Wazuh' '/opt/silent-ridge/open-service.py wazuh'
shortcut 'Evidence' 'thunar /evidence'
shortcut 'How-to guides' 'thunar /evidence/guides'
shortcut 'Autopsy' '/opt/silent-ridge/open-autopsy.sh'
shortcut 'Wireshark' 'wireshark'
shortcut 'Cutter' '/opt/cutter/Cutter.AppImage --appimage-extract-and-run'
chown participant:participant /home/participant/Desktop/*.desktop
chmod 755 /home/participant/Desktop/*.desktop
if ! grep -q '^/opt/silent-ridge/evidence /evidence ' /etc/fstab; then
  printf '/opt/silent-ridge/evidence /evidence none bind,ro 0 0\n' >> /etc/fstab
fi
mountpoint -q /evidence || mount /evidence
mount -o remount,bind,ro /evidence
if [[ -d /opt/silent-ridge/originals ]]; then
  if ! grep -q '^/opt/silent-ridge/originals /originals ' /etc/fstab; then
    printf '/opt/silent-ridge/originals /originals none bind,ro 0 0\n' >> /etc/fstab
  fi
  mountpoint -q /originals || mount /originals
  mount -o remount,bind,ro /originals
fi
systemctl daemon-reload
systemctl enable silent-ridge-desktop.service
echo 'Desktop configured; supply private VNC credentials and endpoints before starting.'
