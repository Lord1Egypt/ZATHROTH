#!/usr/bin/env python3
"""Keep 1-200 varied characters online until Ctrl+C.

    tools/loadtest2.sh 100
    tools/loadtest2.sh clean

Run on the server. Characters have ordinary two-part names, unique levels
from 8 to 1000, varied unlocked outfits/colors, and rotate through every
main town's temple. Account names combine the character's first and last
name. Existing names are skipped. Bots answer pings and turn once a minute
to avoid the idle timeout. Logins respect the service's existing limits.

Ctrl+C, SIGTERM and a closed SSH window log out and delete only this tool's
tagged accounts/characters. A hard kill or reboot leaves accounts behind;
the next run or 'clean' removes them once offline. Concurrent runs of this
tool are refused. Do not run the original loadtest.sh at the same time: it
restores the old record.

The game raises server_config.players_record normally. This tool never
writes or restores that value, including during cleanup. Records include
other online players and never decrease. Normal record broadcasts apply.
No server scripts, configuration, or existing characters are modified.
"""

import argparse
from contextlib import closing, contextmanager
import fcntl
import hashlib
import secrets
import signal
import socket
import sqlite3
import threading
import time
import xml.etree.ElementTree as ET

from loadtest import ROOT, MAX_BOTS, FIRST_MAIN_TOWN, VOCATIONS, load_client, game_usage, say


DATABASE = ROOT / "database" / "zathroth.sqlite3"
# Private ownership tags let cleanup recognize ordinary names safely.
OWNER_EMAIL = "loadtest2@zathroth.invalid"
OWNER_COMMENT = "Managed by tools/loadtest2.sh"
PING_EVERY = 10
TURN_EVERY = 60
REPORT_EVERY = 60
POLL_SECONDS = 0.2
SETTLE_SECONDS = 3
RANDOM = secrets.SystemRandom()
FIRST_NAMES = {
    0: "Adela Alice Amelia Aria Audrey Clara Diana Elena Elise Emma Eva Fiona Freya Grace Hazel Helena Iris Isla Ivy Julia Lara Leah Lena Lila Lily Lina Lydia Maya Mira Nadia Nora Olivia Rose Sara Sofia Stella Thea Vera Violet Willow Zoe".split(),
    1: "Adrian Aiden Alan Alex Arthur Asher Caleb Cedric Cole Daniel Dorian Elias Elliot Ethan Felix Finn Gabriel Henry Hugo Isaac Ivan Jack James Jasper Julian Leo Liam Lucas Marcus Mason Miles Nathan Noah Oliver Oscar Owen Rowan Samuel Simon Theo Victor".split(),
}
LAST_NAMES = "Adler Arden Ashford Bell Bennett Blake Brooks Carter Clarke Collins Dalton Dawson Ellis Evans Fairchild Finch Fletcher Ford Foster Gray Green Hale Hart Hawthorne Hayes Hill Hunter Knight Lane Marsh Miller Morgan North Parker Reed Rivers Rowan Shaw Sterling Stone Vale Walker Ward Wells West Wilder Wood".split()


@contextmanager
def database():
    # mode=rw prevents a wrong path from silently creating an empty database.
    with closing(sqlite3.connect(DATABASE.as_uri() + "?mode=rw", uri=True, timeout=30)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        with db:
            yield db


@contextmanager
def run_lock():
    # Keep the inode in place after unlocking, so every invocation locks the same file.
    with DATABASE.with_suffix(".loadtest2.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("loadtest2 is already running. Stop it with Ctrl+C before starting or cleaning.")
        yield


def owned_accounts(db):
    # Both tags must match, and an account containing any untagged player is excluded.
    return [row[0] for row in db.execute(
        "SELECT a.id FROM accounts a WHERE a.email = ? "
        "AND EXISTS (SELECT 1 FROM players p WHERE p.account_id = a.id AND p.comment = ?) "
        "AND NOT EXISTS (SELECT 1 FROM players p WHERE p.account_id = a.id AND p.comment <> ?)",
        (OWNER_EMAIL, OWNER_COMMENT, OWNER_COMMENT),
    )]


def online_ids(db, account_ids):
    if not account_ids:
        return set()
    marks = ",".join("?" for _ in account_ids)
    return {row[0] for row in db.execute(
        f"SELECT o.player_id FROM players_online o JOIN players p ON p.id = o.player_id "
        f"WHERE p.account_id IN ({marks})", account_ids,
    )}


def remove_accounts(wait_seconds=60):
    deadline = time.monotonic() + wait_seconds
    while True:
        with database() as db:
            accounts = owned_accounts(db)
            online = online_ids(db, accounts)
        if not online:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"{len(online)} loadtest2 characters are still online; accounts kept. Try tools/loadtest2.sh clean after they log out.")
        time.sleep(POLL_SECONDS)
    if not accounts:
        return 0
    time.sleep(SETTLE_SECONDS)  # Allow the game's queued logout saves to finish.
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        accounts = owned_accounts(db)
        if online_ids(db, accounts):
            raise RuntimeError("A loadtest2 character logged back in; accounts kept. Stop it before cleaning.")
        removed = 0
        for account_id in accounts:
            removed += db.execute("DELETE FROM accounts WHERE id = ?", (account_id,)).rowcount
    return removed


def create_accounts(count, stop):
    outfits = {sex: [] for sex in FIRST_NAMES}
    for outfit in ET.parse(ROOT / "data/XML/outfits.xml").getroot():
        if outfit.get("enabled", "yes") == "yes" and outfit.get("unlocked", "no") == "yes":
            sex = int(outfit.get("type"))
            if sex in outfits:
                outfits[sex].append(int(outfit.get("looktype")))
    if not all(outfits.values()):
        raise RuntimeError("No enabled, unlocked outfits found for both sexes.")
    vocations = {int(v.get("id")): v for v in ET.parse(ROOT / "data/XML/vocations.xml").getroot()}
    levels = RANDOM.sample(range(8, 1001), count)
    candidates = {sex: [(first, last) for first in names for last in LAST_NAMES] for sex, names in FIRST_NAMES.items()}
    for names in candidates.values():
        RANDOM.shuffle(names)
    password = secrets.token_urlsafe(24)
    password_hash = hashlib.sha1(password.encode()).hexdigest()
    bots = []
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        towns = [row[0] for row in db.execute(
            "SELECT id FROM towns WHERE id >= ? AND posx > 0 AND posy > 0 ORDER BY id", (FIRST_MAIN_TOWN,),
        )]
        if not towns:
            raise RuntimeError("No main towns found. Start the game once before running this tool.")
        used_players = {row[0].casefold() for row in db.execute("SELECT name FROM players")}
        used_accounts = {row[0].casefold() for row in db.execute("SELECT name FROM accounts")}
        for index, level in enumerate(levels):
            if stop.is_set():
                raise InterruptedError("Stopped while creating characters; creation rolled back.")
            sex = index % 2
            while candidates[sex]:
                first, last = candidates[sex].pop()
                name, account = f"{first} {last}", (first + last).lower()
                if name.casefold() not in used_players and account not in used_accounts:
                    break
            else:
                raise RuntimeError("No unused character/account name combinations left.")
            used_players.add(name.casefold())
            used_accounts.add(account)
            vocation_id = VOCATIONS[index % len(VOCATIONS)]
            vocation = vocations[vocation_id]
            health = 185 + (level - 8) * int(vocation.get("gainhp"))
            mana = 90 + (level - 8) * int(vocation.get("gainmana"))
            capacity = 470 + (level - 8) * int(vocation.get("gaincap"))
            experience = (50 * level ** 3 - 300 * level ** 2 + 850 * level - 600) // 3
            account_id = db.execute(
                "INSERT INTO accounts (name, email, password, creation, premdays, lastday) VALUES (?, ?, ?, ?, 30, ?) RETURNING id",
                (account, OWNER_EMAIL, password_hash, int(time.time()), int(time.time()) + 30 * 86400),
            ).fetchone()[0]
            # Zero position invokes the engine's safe temple placement for the assigned town.
            player_id = db.execute(
                "INSERT INTO players (name, account_id, level, vocation, experience, health, healthmax, mana, manamax, "
                "soul, cap, town_id, sex, looktype, lookhead, lookbody, looklegs, lookfeet, comment) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 100, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (name, account_id, level, vocation_id, experience, health, health, mana, mana, capacity,
                 towns[index % len(towns)], sex, outfits[sex][(index // 2) % len(outfits[sex])],
                 *(RANDOM.randrange(133) for _ in range(4)), OWNER_COMMENT),
            ).fetchone()[0]
            bots.append((account, name, player_id))
    return bots, password, len(towns)


def login(client, account, password, stop):
    deadline = time.monotonic() + 90
    while not stop.is_set():
        reply = client.http_login(account, password)
        session = reply.get("session", {}).get("sessionkey")
        if session:
            return session
        message = reply.get("errorMessage", "No session in login response")
        if "Too many attempts" not in message or time.monotonic() >= deadline:
            raise RuntimeError(message)
        stop.wait(5)
    raise InterruptedError("Stopped during login.")


class Bot(threading.Thread):
    def __init__(self, client, session, name):
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.error = None
        self.name_ = name
        # Retain the partially constructed client so failed handshakes cannot leak sockets.
        self.game = client.GameClient.__new__(client.GameClient)
        try:
            client.GameClient.__init__(self.game, session, name)
            self.game.sock.settimeout(1)
        except BaseException:
            if hasattr(self.game, "sock"):
                self.game.sock.close()
            raise

    def run(self):
        next_ping = next_turn = 0
        direction = 0
        try:
            while not self.stop.is_set():
                now = time.monotonic()
                if now >= next_ping:
                    self.game.send(b"\x1e")
                    next_ping = now + PING_EVERY
                if now >= next_turn:
                    self.game.send(bytes((0x6F + direction,)))
                    direction = (direction + 1) % 4
                    next_turn = now + TURN_EVERY
                try:
                    if not self.game.sock.recv(65536):
                        raise ConnectionError("The server closed the connection")
                except socket.timeout:
                    pass
        except Exception as error:
            self.error = str(error)
        finally:
            try:
                self.game.close()
            except OSError:
                pass
            finally:
                self.game.sock.close()

    def finish(self):
        self.stop.set()
        self.join(timeout=3)
        if self.is_alive():
            try:
                self.game.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.join(timeout=3)


def wait_online(bot, player_id, stop):
    deadline = time.monotonic() + 10
    while not stop.is_set() and bot.is_alive() and time.monotonic() < deadline:
        with database() as db:
            if db.execute("SELECT 1 FROM players_online WHERE player_id = ?", (player_id,)).fetchone():
                return
        stop.wait(POLL_SECONDS)
    if stop.is_set():
        raise InterruptedError("Stopped during login.")
    raise ConnectionError(bot.error or "The game did not confirm this character online within 10 seconds")


def run(count, stop):
    leftovers = remove_accounts(wait_seconds=5)
    if leftovers:
        say(f"Removed {leftovers} leftover loadtest2 accounts.")
    client = load_client()
    say(f"Server {client.HOST}: usage before the run: {game_usage()}")
    running = []
    try:
        bots, password, towns = create_accounts(count, stop)
        say(f"Created {count} characters across {min(count, towns)} of {towns} main towns, levels 8-1000, with varied outfits/colors.")
        say("Logging in: the account service allows 30 logins per address per minute. Ctrl+C stops the run at any time.")
        failures = []
        for account, name, player_id in bots:
            if stop.is_set():
                break
            for attempt in range(3):
                bot = None
                try:
                    session = login(client, account, password, stop)
                    if stop.is_set():
                        break
                    bot = Bot(client, session, name)
                    bot.start()
                    running.append(bot)
                    wait_online(bot, player_id, stop)
                    break
                except InterruptedError:
                    stop.set()
                    break
                except Exception as error:
                    if bot is not None and bot in running:
                        bot.finish()
                        running.remove(bot)
                    elif bot is not None:
                        # Thread startup can fail when host resources are exhausted.
                        bot.game.sock.close()
                    if attempt == 2 or not isinstance(error, OSError):
                        failures.append(f"{name}: {error}")
                        break
                    if stop.wait(4):
                        break
            if running and len(running) % 10 == 0:
                say(f"{sum(bot.is_alive() for bot in running)}/{count} connected...")
        for failure in failures:
            say("Login failed:", failure)
        say(f"{sum(bot.is_alive() for bot in running)}/{count} connected. Staying online until Ctrl+C; player record will be kept.")
        while any(bot.is_alive() for bot in running) and not stop.wait(REPORT_EVERY):
            say(f"{sum(bot.is_alive() for bot in running)}/{count} connected. Server usage: {game_usage()}")
        for bot in running:
            if bot.error:
                say(f"Disconnected: {bot.name_}: {bot.error}")
    finally:
        say("Logging out and cleaning up...")
        # Request all logouts together before joining any individual thread.
        for bot in running:
            bot.stop.set()
        for bot in running:
            bot.finish()
        removed = remove_accounts()
        say(f"Removed {removed} loadtest2 accounts/characters. Player record kept unchanged by cleanup.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bots", help=f"1-{MAX_BOTS}, or 'clean' to remove offline leftovers")
    args = parser.parse_args(argv)
    if args.bots != "clean":
        try:
            count = int(args.bots)
        except ValueError:
            parser.error(f"Use 1-{MAX_BOTS} bots, or 'clean'.")
        if not 1 <= count <= MAX_BOTS:
            parser.error(f"Use 1-{MAX_BOTS} bots.")
    if not DATABASE.is_file():
        parser.error(f"{DATABASE} not found. Run this tool on the server.")
    stop = threading.Event()
    previous = {}
    try:
        # An Event keeps interruption out of SQLite commit/cleanup boundaries.
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[number] = signal.signal(number, lambda signum, frame: stop.set())
        with run_lock():
            if args.bots == "clean":
                say(f"Removed {remove_accounts(wait_seconds=5)} offline loadtest2 accounts. Player record kept.")
            else:
                run(count, stop)
    except InterruptedError:
        say("Stopped.")
    except (OSError, RuntimeError, sqlite3.Error) as error:
        raise SystemExit(str(error))
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    main()
