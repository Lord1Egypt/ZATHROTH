#!/bin/sh
set -eu

cd /opt/zathroth

# Compose mounts the cloned repository here. Run as the folder's owner so the
# database and config.lua written into it stay owned by whoever cloned it.
uid="$(stat -c %u .)"
gid="$(stat -c %g .)"
database_dir="$(dirname "$ZATHROTH_DB_PATH")"
if [ "$(id -u)" = 0 ]; then
	install -d -o "$uid" -g "$gid" "$database_dir"
fi

run() {
	if [ "$(id -u)" = 0 ] && [ "$uid" != 0 ]; then
		exec setpriv --reuid="$uid" --regid="$gid" --clear-groups "$@"
	fi
	exec "$@"
}

case "${1:-game}" in
	accounts)
		run python3 account_manager/server.py
		;;
	game)
		cp config.lua.dist config.lua
		cat >> config.lua <<'LUA'

-- Container settings
serverName = "ZATHROTH"
dataPackDirectory = "data-canary"
mapName = "canary"
toggleDownloadMap = false
generateLuaApiDocs = false

sqliteDatabase = os.getenv("ZATHROTH_DB_PATH")
ip = os.getenv("ZATHROTH_SERVER_IP") or "192.168.1.104"
loginProtocolPort = tonumber(os.getenv("ZATHROTH_LOGIN_PORT") or "7171")
gameProtocolPort = tonumber(os.getenv("ZATHROTH_GAME_PORT") or "7172")
statusProtocolPort = loginProtocolPort
bindOnlyGlobalAddress = false
allowOldProtocol = false
authType = "session"
LUA
		if [ "$(id -u)" = 0 ]; then
			chown "$uid:$gid" config.lua
		fi
		run /usr/local/bin/zathroth
		;;
	*)
		exec "$@"
		;;
esac
