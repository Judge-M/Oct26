#!/usr/bin/env bash
# Idempotent local CA and node certificates for the pinned Wazuh 4.9.2 stack.
# Run on the preparation host; never commit the output (contains private keys).
# Existing certificates are never overwritten unless --force is supplied.
set -euo pipefail
OUT="${1:-./certs}"
DASHBOARD_IP="${2:-127.0.0.1}"
FORCE="${3:-}"
if [[ "$DASHBOARD_IP" == "--force" ]]; then
  DASHBOARD_IP=127.0.0.1
  FORCE=--force
fi
DAYS=825
if [[ "$DASHBOARD_IP" != "127.0.0.1" ]]; then
  [[ "$DASHBOARD_IP" =~ ^[0-9]+(\.[0-9]+){3}$ ]] || {
    echo "Dashboard address must be an IPv4 address" >&2; exit 1;
  }
  IFS=. read -r a b c d <<<"$DASHBOARD_IP"
  for octet in "$a" "$b" "$c" "$d"; do
    (( 10#$octet <= 255 )) || { echo "Invalid dashboard IPv4 address" >&2; exit 1; }
  done
fi
mkdir -p "$OUT"
umask 077

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

if [[ -f "$OUT/root-ca.pem" && "$FORCE" != "--force" ]]; then
  if [[ -f "$OUT/participant.pem" && ! -s "$OUT/participant-key.pem" ]] ||
     [[ -f "$OUT/participant-key.pem" && ! -s "$OUT/participant.pem" ]]; then
    echo "Partial participant certificate exists; restore its pair before retrying" >&2
    exit 1
  fi
  if [[ ! -f "$OUT/participant.pem" ]]; then
    [[ -s "$OUT/root-ca-key.pem" ]] || {
      echo "Existing CA key is missing; cannot add participant certificate" >&2; exit 1;
    }
    issue participant "silent-ridge-participant" "DNS:localhost,IP:127.0.0.1,IP:$DASHBOARD_IP"
  fi
  # The CA certificate is public trust material consumed by a non-root
  # integration job; only its private key must remain owner-readable.
  chmod 644 "$OUT/root-ca.pem"
  echo "Existing CA and Wazuh certificates preserved in $OUT."
  exit 0
fi

openssl genrsa -out "$OUT/root-ca-key.pem" 4096
openssl req -new -x509 -sha256 -key "$OUT/root-ca-key.pem" -out "$OUT/root-ca.pem" \
  -days "$DAYS" -subj "/C=XX/ST=Silent Ridge/L=Exercise/O=Silent Ridge/OU=CA/CN=silent-ridge-ca"
chmod 644 "$OUT/root-ca.pem"

issue indexer "wazuh-indexer" "DNS:wazuh-indexer,DNS:localhost,IP:127.0.0.1"
issue dashboard "wazuh-dashboard" "DNS:wazuh-dashboard,DNS:localhost,IP:127.0.0.1,IP:$DASHBOARD_IP"
issue participant "silent-ridge-participant" "DNS:localhost,IP:127.0.0.1,IP:$DASHBOARD_IP"
issue manager "wazuh-manager" "DNS:wazuh-manager,DNS:localhost,IP:127.0.0.1"
issue admin "admin" "DNS:localhost,IP:127.0.0.1"

echo "Generated local CA and node certificates in $OUT. Trust root-ca.pem explicitly; never disable verification."
