#!/bin/sh
set -eu

cp config.lua.dist config.lua
cat >> config.lua <<'LUA'

-- Container settings
serverName = "ZATHROTH"
dataPackDirectory = "data-canary"
mapName = "canary"
toggleDownloadMap = false
generateLuaApiDocs = false

sqliteDatabase = os.getenv("ZATHROTH_DB_PATH") or "/var/lib/zathroth/zathroth.sqlite3"
ip = os.getenv("ZATHROTH_SERVER_IP") or "192.168.1.104"
loginProtocolPort = tonumber(os.getenv("ZATHROTH_LOGIN_PORT") or "7171")
gameProtocolPort = tonumber(os.getenv("ZATHROTH_GAME_PORT") or "7172")
statusProtocolPort = loginProtocolPort
bindOnlyGlobalAddress = false
allowOldProtocol = false
authType = "session"
LUA

exec /usr/local/bin/zathroth
