#!/bin/bash
# Run on the server to check why the app may not be reachable from outside.
set -e
echo "=== 1. App responding on localhost? ==="
CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8218/api/v1/health)
if [ "$CODE" = "200" ]; then echo "200 (OK)"; else echo "$CODE (expected 200 - redirect or error)"; fi
echo "=== 2. Something listening on 8218? ==="
ss -tlnp 2>/dev/null | grep 8218 || true
PUBLIC_IP=$(curl -s --connect-timeout 2 http://checkip.amazonaws.com 2>/dev/null || echo "unknown")
echo "=== 3. Curl to PUBLIC IP ($PUBLIC_IP) from this server - verbose ==="
echo "If this times out or fails, AWS Security Group likely blocks port 8218."
curl -v --connect-timeout 5 "http://${PUBLIC_IP}:8218/api/v1/health" 2>&1 | head -30
