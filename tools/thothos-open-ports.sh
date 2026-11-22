#!/bin/sh
# Opens ZATHROTH's ports (TCP 7171, 7172, 8088) to the internet through ThothOS's Docker firewall.
#
# ThothOS drops every new connection into a container unless it comes from another container, USB networking or the
# approved Wi-Fi's own subnet, so players on the internet are refused. This adds an optional list of public TCP ports to
# /usr/local/sbin/thothos-docker-firewall (/etc/thothos/docker-public-ports, one number per line or space separated) and
# writes the three ZATHROTH ports into it. Everything else stays blocked. Safe to run again.
#
# Run on the phone:  sudo sh /srv/thothos-data/ZATHROTH/tools/thothos-open-ports.sh
# Undo:              sudo rm /etc/thothos/docker-public-ports && sudo thothos-docker-firewall refresh
# (a ThothOS update that replaces the script drops the patch; run this script again.)
set -eu
SCRIPT=${THOTHOS_FIREWALL_SCRIPT:-/usr/local/sbin/thothos-docker-firewall}
PORTS_FILE=${THOTHOS_PUBLIC_PORTS:-/etc/thothos/docker-public-ports}

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
[ -f "$SCRIPT" ] || { echo "$SCRIPT not found" >&2; exit 1; }

if ! grep -q PUBLIC_PORTS "$SCRIPT"; then
	cp -p "$SCRIPT" "$SCRIPT.bak-before-public-ports"
	awk '
		{ print }
		/^WLAN=/ { print "PUBLIC_PORTS=${THOTHOS_PUBLIC_PORTS:-/etc/thothos/docker-public-ports}" }
		/-i \$USBIF -s 10\.55\.0\.0\/24 -j RETURN/ {
			print "\tif [ -r \"$PUBLIC_PORTS\" ]; then for p in $(cat \"$PUBLIC_PORTS\"); do case $p in \"\"|*[!0-9]*) ;; *) echo \"-A $CHAIN -p tcp --dport $p -j RETURN\";; esac; done; fi"
		}
	' "$SCRIPT.bak-before-public-ports" > "$SCRIPT.new"
	grep -q 'dport \$p' "$SCRIPT.new" && grep -q '^PUBLIC_PORTS=' "$SCRIPT.new" || { rm -f "$SCRIPT.new"; echo "patch did not apply" >&2; exit 1; }
	chmod --reference="$SCRIPT" "$SCRIPT.new"
	mv "$SCRIPT.new" "$SCRIPT"
	echo "patched $SCRIPT (backup: $SCRIPT.bak-before-public-ports)"
fi

mkdir -p "$(dirname "$PORTS_FILE")"
printf '7171\n7172\n8088\n' > "$PORTS_FILE"
"$SCRIPT" refresh
"$SCRIPT" status
