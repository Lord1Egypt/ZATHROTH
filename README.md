# ZATHROTH

ZATHROTH is a Canary-based game server for protocol **15.25**. It runs with SQLite and ships a starter world, a browser account manager, and the HTTP login endpoint used by the Windows client. Docker images are built for Linux AMD64 and ARM64.

## Start on the Linux server

Docker Engine and the Compose plugin are required. The default LAN address is `192.168.1.104`. Authenticate Git for the private repository, then sign in to GHCR with a GitHub classic personal access token that can read the package (`read:packages`).

```sh
git clone https://github.com/Lord1Egypt/ZATHROTH.git
cd ZATHROTH
docker login ghcr.io -u Lord1Egypt
docker compose up -d
docker compose ps
```

The account manager and game share one named Docker volume, `zathroth_world`. SQLite is initialized on the first startup. Use `docker compose logs -f game accounts` to watch startup and `docker compose down` to stop the server while retaining the database.

## Create an account and log in from Windows

1. Open `http://192.168.1.104:8088/` in a browser and sign in with username `1` and password `1`.
2. Create your player account. The manager signs you in automatically so you can create or manage its characters. The shared login can register accounts only.
3. Configure OTClient Redemption on Windows for protocol `1525` and supply the matching game assets. Sign in with the new account and select your character. The login service advertises `192.168.1.104:7172` as the game endpoint. [OTClient 15.25 setup](https://github.com/opentibiabr/otclient/wiki/Tutorial-to-use-OTC-in-Canary-main)

For OTClient Redemption, add this entry to `Servers_init` in `init.lua` with the server list enabled.

```lua
["http://192.168.1.104:8088/login"] = {
    port = 8088,
    protocol = 1525,
    httpLogin = true,
    useAuthenticator = false,
},
```

All three ports use TCP.

| Port | Purpose |
| --- | --- |
| 8088 | Account manager and client HTTP login |
| 7171 | Game server status and protocol login listener |
| 7172 | Game connection |

Run this configuration on a trusted LAN. HTTP login and account management use plain HTTP, and the registration login is shared.

## Configure or update

Optional overrides go in a local `.env` file. `ZATHROTH_SERVER_IP` is advertised to clients, and `ZATHROTH_BIND_IP` selects the Linux host interface to publish on. The bind address defaults to the advertised address.

```dotenv
ZATHROTH_SERVER_IP=192.168.1.104
ZATHROTH_BIND_IP=192.168.1.104
ZATHROTH_LOGIN_PORT=7171
ZATHROTH_GAME_PORT=7172
ZATHROTH_ACCOUNT_PORT=8088
```

Run `git pull`, `docker compose pull`, and `docker compose up -d` to update. Docker picks the image architecture automatically. To build from source on the host, run `docker build -t zathroth:local .` followed by `ZATHROTH_IMAGE=zathroth:local docker compose up -d`.

## Source and contact

ZATHROTH is derived from [Canary](https://github.com/opentibiabr/canary) at revision `666a60f6fef803b043cbaf1c7b5fab219da9bfa9`. The bundled starter map and upstream source are distributed under their existing terms. See [LICENSE](LICENSE) and the source copyright notices.

Compiled by Mohamed Mounir. Contact akim.221992@gmail.com.
