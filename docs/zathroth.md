# ZATHROTH operations guide

How this server is built, deployed and changed. Read it before editing.

## What runs where

- Owner's server: `user@192.168.1.104` (Samsung A50 phone running ThothOS, ARM64, 5.4 GB RAM), folder `/srv/thothos-data/ZATHROTH`. SSH works through the owner's agent socket: `SSH_AUTH_SOCK=/tmp/a50-agent.sock ssh user@192.168.1.104` (the owner loads it with `ssh-add`; never copy keys).
- Compose bind-mounts the cloned repo at `/opt/zathroth`. The image only provides the compiled binary, Python and the entrypoint; every script, NPC, monster, config and the database are read from the clone.
- `game` service: the C++ server on 7171/7172. `accounts` service: `account_manager/server.py`, the SQLite HTTP login (`/login`, `/login.php`) and browser account manager on 8088.
- Map: OTServBR global (`data-otservbr-global`, map `otservbr`). The entrypoint downloads the v3.6.1 `otservbr.otbm` (185 MB, SHA-256 pinned in the Dockerfile) into `data-otservbr-global/world/` on the first start.
- Database: `database/zathroth.sqlite3` (gitignored). Back it up with the game stopped.
- `config.lua` is regenerated from `config.lua.dist` plus container settings on every start. Edit `config.lua.dist`, never `config.lua`.

## Change workflow

1. Edit in `~/Canary/ZATHROTH`, commit and push to `main` (owner rule: every change is committed and pushed).
2. Lua, XML, NPC and config changes need no new image: on the phone run `git pull` then `docker compose restart game`.
3. C++, Python, Dockerfile or entrypoint changes need the GitHub build (`.github/workflows/publish-container.yml`, about 15 minutes). It builds and smoke-tests amd64 and arm64, pushes `ghcr.io/lord1egypt/zathroth` (private package) and refreshes the public release `image` with `zathroth-{amd64,arm64}.tar.gz`. Then on the phone: `git pull && ./up.sh`.
4. `up.sh` loads the release image when ghcr.io refuses the pull. `start.sh` is upstream Canary's bare-metal script; leave it alone.
5. Character edits in SQL (level, skills, coins) only while the player is offline: `docker compose stop game` (saves everyone), back up the database, update through `docker compose exec -T accounts python3`, then `docker compose up -d game`.

## Local testing

- Work in a scratch clone with a `compose.override.yaml` that mounts the edited `docker/entrypoint.sh`, and `ZATHROTH_SERVER_IP=127.0.0.1` in `.env`. Copy a downloaded map into `data-otservbr-global/world/` to skip the download.
- `.github/scripts/zathroth-smoke.py` drives a real 15.25 client: HTTP login, 1/1 Account Manager, account and character creation, privacy. It expects a fresh database. Import it as a module to script other checks (`GameClient`, `http_login`).
- Speech to an NPC after greeting uses talk type 12 (`TALKTYPE_PRIVATE_PN`): send `0x96 0x0c <string>`. Selling is `0x7b <u16 clientId> <u8 count> <u16 amount> <u8 ignoreEquipped>`.
- Canary blocks an IP after more than 5 connections in 5 seconds; the smoke script spaces connections 0.6 s apart.
- CI fails if the game log shows forge "due to no progress" warnings, an NPC price that allows buy-resell profit, or fewer than 21 traders.

## ZATHROTH additions

| Feature | Files |
| --- | --- |
| In-game 1/1 Account Manager | `src/creatures/players/account_manager.{hpp,cpp}` and hooks in `protocolgame.cpp`, `game.cpp`, `iologindata.cpp` |
| HTTP login and browser account manager | `account_manager/` |
| Start town Thais (first town named Thais, else lowest ID) | `account_manager.cpp`, `account_manager/storage.py` |
| One-time move of all characters to Thais when the map changes | `data-otservbr-global/scripts/globalevents/zathroth_world_move.lua` (`server_config` key `zathroth_world`) |
| Zathroth Trader, buys all NPC loot | `data-otservbr-global/npc/zathroth_trader.lua`, placed by `.../globalevents/zathroth_trader_spawn.lua` in 21 depots |
| `/vipset [player]` god command | `data/scripts/talkactions/god/vip_set.lua` |
| `/addcoins player, amount` god command | `data/scripts/talkactions/god/add_coins.lua` |
| Forge creation skips maps without forgeable monsters | `Game::createFiendishMonsters` / `createInfluencedMonsters` in `src/game/game.cpp` |

Existing god commands worth knowing: `/addskill player, level|magic|club|sword|axe|dist|shield|fist, amount`, `/i item`, `/m monster`, `/n npc`, `/s summon`, `/goto player`, `/t` (to temple).

## How to add things

- NPC: copy a similar file in `data-otservbr-global/npc/` (internal name must be unique). Place it with a startup `GlobalEvent` calling `Game.createNpc(name, Position(...))`, or add it to `data-otservbr-global/world/otservbr-npc.xml`. Check placement tiles in the engine (walkable, protection zone, not a house) rather than from raw map bytes; the depot tiles were found that way.
- Shop prices: `sell` is what the NPC pays the player, `buy` is what the player pays. Never let any NPC pay more than another NPC charges for the same item. Canary's own check (`data/scripts/lib/register_npc_type.lua`) only compares the last NPC loaded.
- Events and raids: `data-otservbr-global/raids/`, `data-otservbr-global/scripts/globalevents/`, and the event calendar in `data/json/eventscheduler/` (double XP, loot and similar rates).
- Items: new item IDs need client sprites. Custom gear uses existing IDs with per-item attributes (`ITEM_ATTRIBUTE_NAME`, `DESCRIPTION`, `ARMOR`, `ATTACK`, `DEFENSE`, `WEIGHT`, tier), as `/vipset` does.
- Database migrations in `data-otservbr-global/migrations/` stop at 59, the SQLite baseline; new SQLite schema changes go in migrations numbered 60 and up and must be valid SQLite.
