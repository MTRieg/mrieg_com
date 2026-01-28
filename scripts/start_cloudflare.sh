#!/usr/bin/env bash

#note: as of when I'm writing this comment, no part of my code actually uses this file
#start.sh just runs the command directly

echo "Running Cloudflare tunnel..."
cloudflared tunnel run experimental_tunnel
