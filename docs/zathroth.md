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
| `/vipset [player]` god command: golden armor set, VIP sword, axe, spears, bow, wand, rod, and a quiver of VIP arrows and bolts | `data/scripts/talkactions/god/vip_set.lua` |
| VIP inferno arrows and thunder bolts explode over 9x9 tiles (burst arrows / power bolts with action ID 61530) | `data/scripts/lib/zathroth_vip.lua`, `data/scripts/weapons/scripts/burst_arrow.lua`, `power_bolt.lua` |
| `/addbulkskills player levels` god command (all skills and magic level) | `data/scripts/talkactions/god/add_bulk_skills.lua` |
| VIP item bonuses (skills, magic, health, mana, speed, regeneration, protection, critical, leech, damage, light) while worn, rebuilt on every equipment change and at login | table and refresh in `data/scripts/lib/zathroth_vip.lua`, hook `data/scripts/eventcallbacks/player/zathroth_vip_bonuses.lua` |
| 100-slot VIP backpack (changing backpack, ID 37536, not obtainable elsewhere) | `containersize` in `data/items/items.xml` |
| God arrows (ID 25757, sudden death over 9x9) and god bolts (ID 25758, lightning storm over the exevo gran mas vis area) kill any monster in one god shot and are never used up; gods get them in a god quiver from `/vipset` | `data/scripts/weapons/scripts/zathroth_god_ammo.lua`, `zathrothGodKill` in `zathroth_vip.lua`, item entries in `items.xml`, 25757 alias removed in `Item::CreateItem` (`src/items/item.cpp`) |
| `/setatkspeed N`, `/lootrate N`, `/spawn N` server-wide multipliers, saved in the KV store (`zathroth-rates`) and restored at startup | `data/scripts/lib/zathroth_rates.lua`, `data/scripts/globalevents/zathroth_rates.lua`, `talkactions/god/server_rates.lua`, `create_spawn.lua`; C++ `Game::setAttackSpeedRate`/`setSpawnRate` used by `Player::getAttackSpeed` and `spawn_monster.cpp`; loot in `getLootRandom` (`data/libs/functions/functions.lua`) |
| Gods may attack players | `cannotattackplayer="0"` for group 6 in `data/XML/groups.xml` |
| `/addcoins player, amount` god command | `data/scripts/talkactions/god/add_coins.lua` |
| Forge creation skips maps without forgeable monsters | `Game::createFiendishMonsters` / `createInfluencedMonsters` in `src/game/game.cpp` |

Existing god commands worth knowing: `/addskill player, level|magic|club|sword|axe|dist|shield|fist, amount`, `/i item`, `/m monster`, `/n npc`, `/s summon`, `/goto player`, `/t` (to temple).

## How to add things

- NPC: copy a similar file in `data-otservbr-global/npc/` (internal name must be unique). Place it with a startup `GlobalEvent` calling `Game.createNpc(name, Position(...))`, or add it to `data-otservbr-global/world/otservbr-npc.xml`. Check placement tiles in the engine (walkable, protection zone, not a house) rather than from raw map bytes; the depot tiles were found that way.
- Shop prices: `sell` is what the NPC pays the player, `buy` is what the player pays. Never let any NPC pay more than another NPC charges for the same item. Canary's own check (`data/scripts/lib/register_npc_type.lua`) only compares the last NPC loaded.
- Events and raids: `data-otservbr-global/raids/`, `data-otservbr-global/scripts/globalevents/`, and the event calendar in `data/json/eventscheduler/` (double XP, loot and similar rates).
- Gods have `notgainexperience`, `notgainmana` and `notgainskill`: `/addskill` level and magic do nothing on a god. Set levels directly (`player:setSkillLevel`, `player:setMagicLevel`) as `/addbulkskills` does; skill-try amounts above 2^32 are also lost in the skill-gain event.
- Bows and crossbows fire the first quiver item (right hand) of their ammunition type that the player's level allows; the ammo slot is not used. Check that item, not the ammo slot, when a weapon script needs the ammunition.
- VIP bonuses are keyed by the item's VIP name (only gods can name items). To add a VIP item, add a `ZATHROTH_VIP_BONUSES` entry and make sure the base item has an equip move event in `items.xml`, or the inventory callback never fires for it.
- A wearable container must have the backpack slot in the client data; some fansite backpacks (war backpack 21445) cannot be worn. Test with `player:addItemEx(item, false, CONST_SLOT_BACKPACK)` (17 means cannot be dressed).
- An item ID only exists if the client's `data/items/appearances.dat` has it (crystal bolt 15792 does not). Probe with `ItemType(id):getId()` before using an ID. Names in `items.xml` override the client name, but a stack of more than one shows the plural (`plural=` in `items.xml`, or `ITEM_ATTRIBUTE_PLURALNAME` on an item).
- Ammunition without a `removecount` action is never used up. An item's own `hitchance` replaces the distance-skill hit formula.
- Attack speed cannot go below the scheduler's 50 ms tick, so with a 2 s vocation attack speed the effective maximum is 40x.
- `!commands` lists every talkaction the player's group can use; give new commands a `setDescription`.
- Items: new item IDs need client sprites. Custom gear uses existing IDs with per-item attributes (`ITEM_ATTRIBUTE_NAME`, `DESCRIPTION`, `ARMOR`, `ATTACK`, `DEFENSE`, `WEIGHT`, tier), as `/vipset` does.
- Database migrations in `data-otservbr-global/migrations/` stop at 59, the SQLite baseline; new SQLite schema changes go in migrations numbered 60 and up and must be valid SQLite.
