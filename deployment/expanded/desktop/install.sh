#!/bin/bash
# Run inside the prepared Ubuntu 24.04 desktop template, not the controller host.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run inside the template as root'; exit 1; }
: "${OFFLINE_DEBS:?Path to verified offline package directory}"
: "${IRIS_URL:?Local participant IRIS URL}"
: "${CTFD_URL:?Local participant CTFd URL}"
: "${WAZUH_URL:?Local participant Wazuh URL}"
test -x /opt/autopsy/bin/autopsy
test -x /opt/cutter/Cutter.AppImage
test -f /etc/silent-ridge/vnc-password
# --no-download deliberately fails if the offline dependencies are incomplete.
apt-get --no-download install -y "$OFFLINE_DEBS"/*.deb
for program in startxfce4 Xtigervnc wireshark firefox thunar dbus-run-session; do command -v "$program"; done
if command -v volatility || command -v vol || command -v kape; then
  echo 'Unexpected participant forensic preparation tool installed'; exit 1
fi
id participant >/dev/null 2>&1 || useradd --create-home --shell /bin/bash participant
install -d -o participant -g participant /home/participant/{Desktop,Cases,Workspace,Scratch}
install -d /evidence /opt/silent-ridge/guides
chown participant:participant /etc/silent-ridge/vnc-password
chmod 600 /etc/silent-ridge/vnc-password
cat >/etc/systemd/system/silent-ridge-desktop.service <<'UNIT'
[Unit]
Description=Shared Silent Ridge team desktop
After=network.target
[Service]
User=participant
Environment=HOME=/home/participant
Environment=DISPLAY=:1
ExecStart=/opt/silent-ridge/start-desktop.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
cat >/opt/silent-ridge/start-desktop.sh <<'DESKTOP'
#!/bin/bash
set -euo pipefail
Xtigervnc :1 -geometry 1440x900 -depth 24 -SecurityTypes VncAuth -PasswordFile /etc/silent-ridge/vnc-password -AlwaysShared -localhost no &
vnc_pid=$!
trap 'kill "$vnc_pid"' EXIT
for attempt in {1..20}; do test -S /tmp/.X11-unix/X1 && break; sleep .2; done
dbus-run-session -- startxfce4
DESKTOP
chmod 755 /opt/silent-ridge/start-desktop.sh
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
shortcut 'Incident queue' "firefox $IRIS_URL/silent-ridge"
shortcut 'Questions and help' "firefox $CTFD_URL/silent-ridge"
shortcut 'Wazuh' "firefox $WAZUH_URL"
shortcut 'Evidence' 'thunar /evidence'
shortcut 'How-to guides' 'thunar /evidence/guides'
shortcut 'Autopsy' '/opt/autopsy/bin/autopsy'
shortcut 'Wireshark' 'wireshark'
shortcut 'Cutter' '/opt/cutter/Cutter.AppImage --appimage-extract-and-run'
chown participant:participant /home/participant/Desktop/*.desktop
chmod 755 /home/participant/Desktop/*.desktop
systemctl enable silent-ridge-desktop.service
echo 'Template configured. Mount released evidence read-only, restrict VNC to guacd, and rehearse before cloning.'
