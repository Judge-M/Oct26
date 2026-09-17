#!/usr/bin/env bash
# Install participant launchers and desktop shortcuts inside the container image.
# Mirrors deployment/expanded/desktop/configure-image.sh for the Docker path.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run inside the image build as root'; exit 1; }

test -x /opt/autopsy/bin/autopsy
test -f /opt/cutter/Cutter.AppImage
id participant >/dev/null 2>&1 || useradd --create-home --uid 1000 --shell /bin/bash participant
install -d -o participant -g participant /home/participant/Desktop /home/participant/Cases \
  /home/participant/Workspace /home/participant/Scratch
install -d /etc/silent-ridge /opt/silent-ridge
mkdir -p /evidence /originals

ln -sfn /opt/firefox/firefox /usr/local/bin/firefox
chmod 755 /opt/cutter/Cutter.AppImage
ldconfig
for tool in startxfce4 Xtigervnc wireshark firefox thunar dbus-run-session zenity; do command -v "$tool"; done

install -m 755 /opt/silent-ridge/helpers/open-service.py /opt/silent-ridge/open-service.py
install -m 755 /opt/silent-ridge/helpers/open-autopsy.sh /opt/silent-ridge/open-autopsy.sh

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
echo 'Desktop configured for the container; supply VNC credentials and endpoints at runtime.'
