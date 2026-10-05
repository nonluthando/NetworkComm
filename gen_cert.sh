#!/bin/sh
# Generate a self-signed certificate for local testing.
# The client pins this certificate as its trust root (--cafile certs/server.crt).
set -e
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout certs/server.key -out certs/server.crt \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 certs/server.key
echo "Wrote certs/server.crt and certs/server.key"
