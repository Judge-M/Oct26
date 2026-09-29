#!/usr/bin/env bash
# Run ONLY inside the disposable, prepared desktop build guest before export.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Root required'; exit 1; }
test -f /opt/silent-ridge/prepared-case/WS17/WS17.aut
test -f /opt/silent-ridge/originals/windows/WS17.raw
test -f /opt/silent-ridge/evidence/prepared/memory-processes.json
systemctl stop silent-ridge-desktop.service
systemctl disable walinuxagent.service
systemctl stop walinuxagent.service
systemctl disable hv-vss-daemon.service hv-kvp-daemon.service hv-fcopy-daemon.service
install -d /opt/silent-ridge/provenance
dpkg-query -W > /opt/silent-ridge/provenance/packages.tsv
uname -r > /opt/silent-ridge/provenance/validated-kernel.txt
# All paths below are disposable guest build/test state, never host paths.
rm -rf /home/participant/.autopsy /home/participant/.cache /home/participant/.mozilla
rm -rf /home/participant/.local/state /home/participant/.config/Cutter
rm -rf /home/participant/Cases /opt/silent-ridge/cases
install -d -o participant -g participant /home/participant/Cases
cp -a /opt/silent-ridge/prepared-case/WS17 /home/participant/Cases/WS17
chown -R participant:participant /home/participant/Cases
rm -f /home/participant/desktop-test.png /home/participant/.bash_history
rm -f /etc/silent-ridge/vnc-password /etc/silent-ridge/endpoints.json
rm -f /root/.ssh/authorized_keys /root/.bash_history /etc/ssh/ssh_host_*
if id builder >/dev/null 2>&1; then
  usermod --lock --shell /usr/sbin/nologin builder
  rm -rf /home/builder
fi
rm -f /etc/sudoers.d/90-cloud-init-users
rm -f /etc/cloud/cloud.cfg.d/10-azure-kvp.cfg /etc/cloud/cloud.cfg.d/90-azure.cfg
cat >/etc/cloud/cloud.cfg.d/99-silent-ridge-datasources.cfg <<'EOF'
datasource_list: [ NoCloud, Ec2, None ]
EOF
apt-get clean
cloud-init clean --logs --machine-id --seed
rm -rf /var/lib/waagent /var/lib/dhcp/* /var/lib/systemd/network/*
find /var/log -type f -exec truncate -s 0 {} +
find /tmp /var/tmp -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
rm -f /var/lib/systemd/random-seed
sync
fstrim -av
systemctl poweroff
