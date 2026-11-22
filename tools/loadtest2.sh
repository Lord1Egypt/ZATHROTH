#!/bin/sh
# Usage: tools/loadtest2.sh <bots> [--no-delete | -no delete] | clean | --help
cd "$(dirname "$0")/.." && exec python3 -u tools/loadtest2.py "$@"
