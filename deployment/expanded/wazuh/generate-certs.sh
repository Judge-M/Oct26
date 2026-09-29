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
CRL_PORT="${RIDGE_CRL_PORT:-8080}"
[[ "$CRL_PORT" =~ ^[0-9]+$ ]] && (( 10#$CRL_PORT > 0 && 10#$CRL_PORT <= 65535 )) || {
  echo "RIDGE_CRL_PORT must be a TCP port from 1 through 65535" >&2; exit 1;
}
CRL_URL="http://$DASHBOARD_IP:$CRL_PORT/root-ca.crl"
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
crlDistributionPoints=URI:$CRL_URL
EOF
  openssl x509 -req -in "$OUT/$name.csr" -CA "$OUT/root-ca.pem" -CAkey "$OUT/root-ca-key.pem" \
    -CAcreateserial -out "$OUT/$name.pem" -days "$DAYS" -sha256 -extfile "$OUT/$name.ext"
  rm -f "$OUT/$name.csr" "$OUT/$name.ext"
  chmod 600 "$OUT/$name-key.pem"
}

generate_crl() {
  : >"$OUT/index.txt"
  [[ -s "$OUT/crlnumber" ]] || printf '1000\n' >"$OUT/crlnumber"
  cat >"$OUT/crl.cnf" <<EOF
[ca]
default_ca=CA_default
[CA_default]
database=$OUT/index.txt
crlnumber=$OUT/crlnumber
certificate=$OUT/root-ca.pem
private_key=$OUT/root-ca-key.pem
default_md=sha256
default_crl_days=$DAYS
policy=policy_any
[policy_any]
commonName=optional
EOF
  openssl ca -batch -gencrl -config "$OUT/crl.cnf" -out "$OUT/root-ca.crl.pem"
  openssl crl -in "$OUT/root-ca.crl.pem" -outform DER -out "$OUT/root-ca.crl"
  openssl crl -in "$OUT/root-ca.crl.pem" -noout -verify -CAfile "$OUT/root-ca.pem"
  chmod 644 "$OUT/root-ca.crl" "$OUT/root-ca.crl.pem"
  rm -f "$OUT/crl.cnf"
}

verify_revocation_material() {
  [[ -s "$OUT/root-ca.crl" ]] || {
    echo "Existing certificates have no published CRL; rerun with --force to rotate them" >&2
    exit 1
  }
  for name in dashboard participant; do
    openssl x509 -in "$OUT/$name.pem" -noout -ext crlDistributionPoints |
      grep -F "$CRL_URL" >/dev/null || {
        echo "Existing $name certificate lacks CRL URL $CRL_URL; rerun with --force" >&2
        exit 1
      }
  done
  openssl crl -in "$OUT/root-ca.crl" -inform DER -noout -verify -CAfile "$OUT/root-ca.pem"
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
    generate_crl
  fi
  # The CA certificate is public trust material consumed by a non-root
  # integration job; only its private key must remain owner-readable.
  chmod 644 "$OUT/root-ca.pem"
  verify_revocation_material
  echo "Existing CA and Wazuh certificates preserved in $OUT."
  exit 0
fi

openssl genrsa -out "$OUT/root-ca-key.pem" 4096
openssl req -new -x509 -sha256 -key "$OUT/root-ca-key.pem" -out "$OUT/root-ca.pem" \
  -days "$DAYS" -subj "/C=XX/ST=Silent Ridge/L=Exercise/O=Silent Ridge/OU=CA/CN=silent-ridge-ca" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"
chmod 644 "$OUT/root-ca.pem"

issue indexer "wazuh-indexer" "DNS:wazuh-indexer,DNS:localhost,IP:127.0.0.1"
issue dashboard "wazuh-dashboard" "DNS:wazuh-dashboard,DNS:localhost,IP:127.0.0.1,IP:$DASHBOARD_IP"
issue participant "silent-ridge-participant" "DNS:localhost,IP:127.0.0.1,IP:$DASHBOARD_IP"
issue manager "wazuh-manager" "DNS:wazuh-manager,DNS:localhost,IP:127.0.0.1"
issue admin "admin" "DNS:localhost,IP:127.0.0.1"
generate_crl
verify_revocation_material

echo "Generated local CA, node certificates, and signed CRL in $OUT. Publish $CRL_URL and trust root-ca.pem explicitly; never disable verification."
