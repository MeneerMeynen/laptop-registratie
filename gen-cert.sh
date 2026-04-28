#!/usr/bin/env bash
set -euo pipefail

# Detect LAN IP — macOS uses ipconfig, Linux uses hostname -I
detect_ip() {
  if [[ "$(uname)" == "Darwin" ]]; then
    for iface in en0 en1 $(ifconfig -l 2>/dev/null); do
      IP=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
      [[ -n "$IP" ]] && echo "$IP" && return
    done
  else
    # ip route is available on all Linux (incl. Ubuntu Core); hostname may not be
    ip route get 1.1.1.1 2>/dev/null | awk '/src/{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}'
  fi
}

LOCAL_IP=$(detect_ip)

if [[ -z "$LOCAL_IP" ]]; then
  echo "ERROR: Could not detect a local IP address." >&2
  exit 1
fi

echo "Detected IP: $LOCAL_IP"

# Install mkcert if missing
if ! command -v mkcert &>/dev/null; then
  echo "mkcert not found — installing..."
  if [[ "$(uname)" == "Darwin" ]]; then
    brew install mkcert nss
  elif command -v apt-get &>/dev/null; then
    sudo apt-get install -y libnss3-tools
    ARCH=$(dpkg --print-architecture)
    LATEST=$(curl -sSL https://api.github.com/repos/FiloSottile/mkcert/releases/latest \
      | grep "browser_download_url.*linux-${ARCH}" | cut -d'"' -f4)
    sudo curl -sSL "$LATEST" -o /usr/local/bin/mkcert
    sudo chmod +x /usr/local/bin/mkcert
  else
    echo "ERROR: Cannot auto-install mkcert on this OS. Install it manually: https://github.com/FiloSottile/mkcert" >&2
    exit 1
  fi
fi

mkcert -install

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
