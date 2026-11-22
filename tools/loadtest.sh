#!/bin/sh
# Usage: tools/loadtest.sh <bots> <seconds>   (see tools/loadtest.py)
cd "$(dirname "$0")/.." && exec python3 -u tools/loadtest.py "$@"
