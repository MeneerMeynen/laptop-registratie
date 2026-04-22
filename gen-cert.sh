#!/usr/bin/env bash
set -euo pipefail

# Detect current LAN IP (en0 first, fall back to en1, then any other interface)
LOCAL_IP=""
for iface in en0 en1 $(ifconfig -l 2>/dev/null); do
  IP=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
  if [[ -n "$IP" ]]; then
    LOCAL_IP="$IP"
    break
  fi
done

if [[ -z "$LOCAL_IP" ]]; then
  echo "ERROR: Could not detect a local IP address." >&2
  exit 1
fi

echo "Detected IP: $LOCAL_IP"

# Generate cert for the detected IP + localhost fallback
CAROOT="$(mkcert -CAROOT)"
mkdir -p certs

mkcert \
  -cert-file certs/cert.pem \
  -key-file  certs/key.pem \
  "$LOCAL_IP" localhost 127.0.0.1

# Copy the root CA so mobile devices can install it via http://<ip>/rootCA.crt
cp "${CAROOT}/rootCA.pem" certs/rootCA.crt

echo ""
echo "Cert generated for: $LOCAL_IP, localhost, 127.0.0.1"
echo "Files written to:   certs/cert.pem, certs/key.pem, certs/rootCA.crt"
echo ""
echo "Run 'docker compose up --build' to apply the new cert."
echo ""
echo "To install the CA on iOS/Android, open:"
echo "  http://$LOCAL_IP/rootCA.crt"
