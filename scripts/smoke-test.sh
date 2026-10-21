#!/usr/bin/env bash
# Smoke test a running instance: certificate chain, HTTP/2, ingest and read-back.
# Usage: scripts/smoke-test.sh [base-url] [ca-file]
set -euo pipefail

base="${1:-https://localhost:8443}"
ca="${2:-certs/ca.crt}"

api() { curl --silent --show-error --fail --http2 --cacert "$ca" "$@"; }

# Wait up to 30 s for the service to start answering.
for _ in $(seq 30); do
  api --output /dev/null "$base/healthz" 2>/dev/null && break
  sleep 1
done

version=$(api --output /dev/null --write-out '%{http_version}' "$base/healthz")
if [ "$version" != "2" ]; then
  echo "FAIL expected HTTP/2, got HTTP/$version" >&2
  exit 1
fi
echo "ok   HTTP/2 over TLS, server certificate verified against $ca"

api --output /dev/null -X POST "$base/frames" -H 'Content-Type: application/json' \
  --data '{"frames": [{"id": 256, "data": "B80B695A00000000"}]}'
echo "ok   POST /frames"

rpm=$(api "$base/signals/motor_rpm" | python3 -c 'import json, sys; print(json.load(sys.stdin)["value"])')
if [ "$rpm" != "3000.0" ]; then
  echo "FAIL expected motor_rpm 3000.0, got $rpm" >&2
  exit 1
fi
echo "ok   GET /signals/motor_rpm -> $rpm rpm"