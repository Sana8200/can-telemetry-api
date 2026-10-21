#!/usr/bin/env bash
#
# Makes a throwaway CA and a server cert signed by it, so the API can run over
# TLS locally and in CI. Dev only, don't use these anywhere real.
#
#   scripts/make-certs.sh [dir]      (default dir is certs/)
#   curl --cacert certs/ca.crt https://localhost:8443/healthz
#
# -addext needs OpenSSL 1.1.1+

set -euo pipefail

out="${1:-certs}"
days=365
mkdir -p "$out"
umask 077 # keys stay private, the .crt files get opened up at the end

# CA
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$out/ca.key"
openssl req -x509 -new -key "$out/ca.key" -sha256 -days "$days" \
  -subj "/CN=CAN Telemetry Dev CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -out "$out/ca.crt"

# Server key + CSR
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$out/server.key"
openssl req -new -key "$out/server.key" -subj "/CN=can-telemetry" -out "$out/server.csr"

# Clients check the hostname against the SANs, not the CN.
# The svc names are for when it's running in k8s.
cat >"$out/server.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:can-telemetry,DNS:can-telemetry.default.svc,DNS:can-telemetry.default.svc.cluster.local
EOF
openssl x509 -req -in "$out/server.csr" -CA "$out/ca.crt" -CAkey "$out/ca.key" \
  -CAcreateserial -days "$days" -sha256 -extfile "$out/server.ext" -out "$out/server.crt"

rm -f "$out/server.csr" "$out/server.ext" "$out/ca.srl"
chmod 644 "$out/ca.crt" "$out/server.crt"
openssl verify -CAfile "$out/ca.crt" "$out/server.crt"
