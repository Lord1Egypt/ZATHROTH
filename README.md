# ZATHROTH

ZATHROTH is a Canary-based game server for protocol **15.25**. It runs with SQLite on the full OTServBR global map (Thais, Carlin, Venore and every other town, with their monsters, NPCs and quests), and ships an in-game 1/1 Account Manager, a browser account manager, and the HTTP login server used by the Windows client. Docker images are built for Linux AMD64 and ARM64.

## Start on the Linux server

Docker Engine with the Compose plugin and `curl` are required. The default LAN address is `192.168.1.104`. No registry login is needed.

```sh
git clone https://github.com/Lord1Egypt/ZATHROTH.git
cd ZATHROTH
./up.sh
```

`up.sh` downloads the Docker image for your CPU (x86_64 or arm64) from the repository's public [image release](https://github.com/Lord1Egypt/ZATHROTH/releases/tag/image), loads it, and runs `docker compose up -d`. Once the image is loaded, plain `docker compose up -d` and `docker compose down` work as usual.

The server runs from the folder you cloned. Compose mounts it into both containers, so the game reads `data/`, `data-otservbr-global/` and `config.lua.dist` from it. On the first start the game downloads the 185 MB map into `data-otservbr-global/world/otservbr.otbm`, checks its SHA-256, and creates the SQLite database in `database/zathroth.sqlite3`. Loading the map takes a few minutes on small ARM boards, and the game server needs about 1.5 GB of RAM. New characters start in Thais. The containers run as the folder's owner, so these files stay yours. Edit scripts or `config.lua.dist` in the folder and run `docker compose restart` to apply them. Use `docker compose logs -f game accounts` to watch startup, and `docker compose down` to stop the server. Your accounts and characters stay in `database/`.

To back up the server, stop it with `docker compose down` and copy the `database/` folder.

## Create an account and log in from Windows

The game client logs in over HTTP, so configure the client first (below). Then:

1. In the client, log in with account `1` and password `1`. Select the **Account Manager** character.
2. The Account Manager stands still at the temple and talks to you in the Local Chat channel. Only you can see what you type. Say `account`, then answer its questions to choose a password and an account name.
3. Once the account exists, the same Account Manager helps you create characters. Say `character`, then pick a name, `male` or `female`, and a vocation.
4. Log out and log in with your new account. Your characters are listed with an **Account Manager** entry. Use that entry at any time to add characters, `delete` one (deletion happens after 7 days), or change your `password`.

You can do the same in a browser at `http://192.168.1.104:8088/`. Sign in there with `1` / `1` to register an account with an email address.

The `accounts` service is the HTTP login server, the SQLite counterpart of OpenTibiaBR's login-server. It answers `/login` and `/login.php` with the same JSON, and its sessions are checked by the game server. It advertises `192.168.1.104:7172` as the game endpoint.

With OTClient Redemption 4.2, extract its source ZIP and place `otclient_gl_x64.exe` from the Windows OpenGL ZIP beside `init.lua`. Supply the matching assets in `data/things/1525/`. [OTClient 4.2 downloads](https://github.com/opentibiabr/otclient/releases/tag/4.2) · [15.25 asset setup](https://github.com/opentibiabr/otclient/wiki/Tutorial-to-use-OTC-in-Canary-main)

Add this entry to `Servers_init` in `init.lua` with the server list enabled.

```lua
["http://192.168.1.104:8088/login"] = {
    port = 8088,
    protocol = 1525,
    httpLogin = true,
    useAuthenticator = false,
},
```

A client that asks for a login URL instead uses `http://192.168.1.104:8088/login.php`.

All three ports use TCP.

| Port | Purpose |
| --- | --- |
| 8088 | Account manager and client HTTP login |
| 7171 | Game server status and protocol login listener |
| 7172 | Game connection |

## HTTPS

The `https` profile adds a Caddy container that serves the account service over HTTPS on ports 80 and 443. It gets a Let's Encrypt certificate for your host name by itself and renews it.

1. Forward TCP 80 and 443 to the server too, and make sure the host name (for example a No-IP name) already points at your public address.
2. Add this to `.env`:

```dotenv
ZATHROTH_DOMAIN=yourname.ddns.net
ZATHROTH_SERVER_IP=yourname.ddns.net
ZATHROTH_BIND_IP=192.168.1.104
ZATHROTH_LAN_IP=192.168.1.104
COMPOSE_PROFILES=https
# First run only: a test certificate, so a mistake does not use up Let's Encrypt's real limits.
ZATHROTH_ACME_CA=https://acme-staging-v02.api.letsencrypt.org/directory
```

`ZATHROTH_SERVER_IP` is the game address sent to players on the internet. `ZATHROTH_BIND_IP` must then be the server's own LAN address, since the ports cannot be bound to a host name. Players on your home network are sent `ZATHROTH_LAN_IP` instead, because many routers cannot connect to their own public address.

3. Run `./up.sh`. When the log shows the test certificate was obtained (`docker compose logs proxy`), delete the `ZATHROTH_ACME_CA` line and run `./up.sh` again for the real one. Players open `https://yourname.ddns.net/` in a browser, and a client that supports HTTPS logins uses `https://yourname.ddns.net/login`.

Certificates are kept in `database/caddy` (Caddy writes them as root, so removing that folder needs `sudo`). Let's Encrypt limits failed attempts, so check the host name resolves and the ports are forwarded before the first start. Plain HTTP on port 8088 keeps working for clients without HTTPS support; once every client uses HTTPS, remove the 8088 forward from the router. The game connection on 7172 is not HTTPS.

The account service trusts the `X-Forwarded-For` and `X-Forwarded-Proto` headers only from the `proxy` container, so the limits below see each visitor's real address and the session cookie is marked `Secure`.

## Security

Over plain HTTP (port 8088), passwords and game session keys are not encrypted on the way. Use the HTTPS profile above before inviting players you do not know.

The account service and the in-game Account Manager limit abuse:

- **CAPTCHA:** creating an account in the browser needs a picture CAPTCHA (a few characters drawn as warped strokes, generated by the server itself, nothing is sent to a third party). Sign-in asks for it after 3 failed attempts from the same address. Set `ZATHROTH_CAPTCHA=off` in `.env` to remove it on a private LAN.
- **Failed logins:** after 10 failures an address is blocked for up to 15 minutes, and after 40 failures an account name is blocked for up to an hour. This applies to the browser and to the game client's login, which cannot show a CAPTCHA.
- **New accounts:** at most 5 per address per day and 60 per hour for the whole server, in the browser and in game. Raise `REGISTRATIONS_PER_IP` in `account_manager/guard.py` (and `MAX_ACCOUNTS_PER_ADDRESS` in `src/creatures/players/account_manager.cpp`) if many players share one address.
- **Connections:** at most 8 at a time from one address, 64 in total, and every connection is cut after 30 seconds.
- **Passwords:** 8 to 128 characters, not on a list of common passwords, not made of fewer than 4 different characters, and not containing the account name.

The shared `1`/`1` login is not counted as a guess and always works; it only opens the Account Manager.

## Configure or update

Optional overrides go in a local `.env` file. `ZATHROTH_SERVER_IP` is advertised to clients, and `ZATHROTH_BIND_IP` selects the Linux host interface to publish on. The bind address defaults to the advertised address.

```dotenv
ZATHROTH_SERVER_IP=192.168.1.104
ZATHROTH_BIND_IP=192.168.1.104
ZATHROTH_CAPTCHA=on
ZATHROTH_LOGIN_PORT=7171
ZATHROTH_GAME_PORT=7172
ZATHROTH_ACCOUNT_PORT=8088
```

Run `git pull` and `./up.sh` to update. Every push to `main` rebuilds and tests both architectures, then refreshes the image release. Docker picks the image architecture automatically. To build from source on the host, run `docker build -t zathroth:local .` followed by `ZATHROTH_IMAGE=zathroth:local docker compose up -d`.

## Source and contact

ZATHROTH is derived from [Canary](https://github.com/opentibiabr/canary) at revision `666a60f6fef803b043cbaf1c7b5fab219da9bfa9`. The bundled starter map and upstream source are distributed under their existing terms. See [LICENSE](LICENSE) and the source copyright notices.

Compiled by Mohamed Mounir. Contact akim.221992@gmail.com.
