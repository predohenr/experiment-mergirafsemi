#!/bin/bash

# Retrieve host user and group IDs from environment variables or default to root
HOST_USER_ID=${HOST_USER_ID:-9001}
HOST_GROUP_ID=${HOST_GROUP_ID:-9001}

# Create a user and group with the same IDs as the host user
groupadd -g $HOST_GROUP_ID mygroup 2>/dev/null || true
useradd -u $HOST_USER_ID -g mygroup -m myuser 2>/dev/null || true

# Change ownership of the mounted directory
chown -R myuser:mygroup /usr/src/miningframework

# Switch to the new user and execute the container's main process
exec gosu myuser "$@"