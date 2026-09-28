#!/usr/bin/with-contenv bash
# Runs after the pinned image has seeded /etc/filebeat, before its services.
set -euo pipefail

credential=/run/secrets/wazuh_indexer_credential
[[ -s "$credential" ]] || { echo 'Wazuh Filebeat indexer credential is missing' >&2; exit 1; }
IFS=: read -r username password < "$credential" || [[ -n "${username:-}" ]]
[[ "$username" == admin && -n "$password" ]] || {
  echo 'Wazuh Filebeat credential must contain the generated admin identity' >&2
  exit 1
}
[[ -s /etc/filebeat/wazuh-template.json ]] || {
  echo 'Pinned Wazuh image did not seed its Filebeat template' >&2
  exit 1
}

cat > /etc/filebeat/filebeat.yml <<'YAML'
filebeat.modules:
  - module: wazuh
    alerts:
      enabled: true
    archives:
      enabled: false
setup.template.json.enabled: true
setup.template.overwrite: true
setup.template.json.path: /etc/filebeat/wazuh-template.json
setup.template.json.name: wazuh
setup.ilm.enabled: false
output.elasticsearch:
  hosts: ["https://wazuh-indexer:9200"]
  username: admin
  password: "${RIDGE_FILEBEAT_PASSWORD}"
  ssl.certificate_authorities: ["/etc/ssl/certs/silent-ridge-root-ca.pem"]
logging.metrics.enabled: false
seccomp:
  default_action: allow
  syscalls:
    - action: allow
      names: [rseq]
YAML
chmod 600 /etc/filebeat/filebeat.yml

filebeat keystore create --force -c /etc/filebeat/filebeat.yml >/dev/null
printf '%s' "$password" | filebeat keystore add RIDGE_FILEBEAT_PASSWORD \
  --stdin --force -c /etc/filebeat/filebeat.yml >/dev/null
unset password
filebeat test config -c /etc/filebeat/filebeat.yml >/dev/null
