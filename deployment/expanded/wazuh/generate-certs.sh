#!/usr/bin/env bash
# Idempotent local CA and node certificates for the pinned Wazuh 4.9.2 stack.
# Run on the preparation host; never commit the output (contains private keys).
# Existing certificates are never overwritten unless --force is supplied.
set -euo pipefail
OUT="${1:-./certs}"
FORCE="${2:-}"
DAYS=825
mkdir -p "$OUT"
umask 077

if [[ -f "$OUT/root-ca.pem" && "$FORCE" != "--force" ]]; then
  echo "Certificates already exist in $OUT; leaving them untouched."
  exit 0
fi

openssl genrsa -out "$OUT/root-ca-key.pem" 4096
openssl req -new -x509 -sha256 -key "$OUT/root-ca-key.pem" -out "$OUT/root-ca.pem" \
  -days "$DAYS" -subj "/C=XX/ST=Silent Ridge/L=Exercise/O=Silent Ridge/OU=CA/CN=silent-ridge-ca"

issue() {
  local name="$1" cn="$2" san="$3"
  openssl genrsa -out "$OUT/$name-key.pem" 2048
  openssl req -new -key "$OUT/$name-key.pem" -out "$OUT/$name.csr" \
    -subj "/C=XX/ST=Silent Ridge/L=Exercise/O=Silent Ridge/OU=Node/CN=$cn"
  cat >"$OUT/$name.ext" <<EOF
subjectAltName=$san
extendedKeyUsage=serverAuth,clientAuth
EOF
  openssl x509 -req -in "$OUT/$name.csr" -CA "$OUT/root-ca.pem" -CAkey "$OUT/root-ca-key.pem" \
    -CAcreateserial -out "$OUT/$name.pem" -days "$DAYS" -sha256 -extfile "$OUT/$name.ext"
  rm -f "$OUT/$name.csr" "$OUT/$name.ext"
  chmod 600 "$OUT/$name-key.pem"
}

issue indexer "wazuh-indexer" "DNS:wazuh-indexer,DNS:localhost,IP:127.0.0.1"
issue dashboard "wazuh-dashboard" "DNS:wazuh-dashboard,DNS:localhost,IP:127.0.0.1"
issue manager "wazuh-manager" "DNS:wazuh-manager,DNS:localhost,IP:127.0.0.1"
issue admin "admin" "DNS:localhost,IP:127.0.0.1"

echo "Generated local CA and node certificates in $OUT. Trust root-ca.pem explicitly; never disable verification."
