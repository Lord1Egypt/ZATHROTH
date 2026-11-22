#!/bin/sh
# Start ZATHROTH without a registry login: if the image cannot be pulled,
# load the one for this CPU from the public GitHub release.
set -eu
cd "$(dirname "$0")"

image="ghcr.io/lord1egypt/zathroth:latest"
if ! docker pull -q "$image" >/dev/null 2>&1; then
	case "$(uname -m)" in
		x86_64 | amd64) arch=amd64 ;;
		aarch64 | arm64) arch=arm64 ;;
		*)
			echo "ZATHROTH images are built for x86_64 and arm64, not $(uname -m)." >&2
			exit 1
			;;
	esac
	echo "Downloading the ZATHROTH image for $arch..."
	curl -fL "https://github.com/Lord1Egypt/ZATHROTH/releases/download/image/zathroth-$arch.tar.gz" | gunzip | docker load
fi

mkdir -p database/caddy
docker compose up -d
docker compose ps
