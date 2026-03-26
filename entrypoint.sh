#!/bin/bash
set -e

IDENTITY_FILE="/app/identity/earthserv.id"

# If EARTHSERV_PRIVATE_KEY is set, write it to the identity file
if [ -n "$EARTHSERV_PRIVATE_KEY" ]; then
    mkdir -p /app/identity
    echo "$EARTHSERV_PRIVATE_KEY" | base64 -d > "$IDENTITY_FILE"
    echo "Loaded identity from EARTHSERV_PRIVATE_KEY env var"
fi

exec python3 -u earthserv.py ./www -i "$IDENTITY_FILE" -c ./rns_config
