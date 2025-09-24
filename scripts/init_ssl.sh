#!/usr/bin/env bash
DOMAIN=${1:-localhost}
openssl req -x509 -newkey rsa:4096 -sha256 -days 365 \
  -nodes -keyout ssl/key.pem -out ssl/cert.pem \
  -subj "/CN=$DOMAIN"
echo "✅ SSL certs created at ssl/key.pem ssl/cert.pem"
