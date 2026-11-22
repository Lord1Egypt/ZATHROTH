#!/usr/bin/env python3
"""Load test: log in many test characters at once, keep them online, then remove them.

    tools/loadtest.sh <bots> <seconds>        for example: tools/loadtest.sh 100 300

Run it on the server, from the repository folder. Each bot gets its own
account (loadtest-001, ...) and a character clearly named "Loadtest Aa",
"Loadtest Ab", ... spread over the main towns and the five start vocations.
The bots log in through the real HTTP login and game handshake, answer the
server's ping, stay for <seconds>, log out, and every test account is deleted
afterwards (also after Ctrl+C, an error or a closed SSH window). Limits:
1-200 bots, 10-900 seconds. The player record the bots raise is put back in
the database (the running game keeps reporting the raised peak until it
restarts), and the in-game "New record" message is not broadcast for them.

    tools/loadtest.sh clean                   removes test accounts left by a run that was killed

While a test runs the bots count as online players, also for server lists.
"""

import importlib.util
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import hashlib
import struct
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "database" / "zathroth.sqlite3"
ACCOUNT_PREFIX = "loadtest-"
CHARACTER_PREFIX = "Loadtest "
MAX_BOTS = 200
MAX_SECONDS = 900
# Towns 1-4 are the tutorial, Dawnport, Rookgaard and Island of Destiny.
FIRST_MAIN_TOWN = 5
VOCATIONS = (1, 2, 3, 4, 9)
PING_EVERY = 10


def load_client():
    spec = importlib.util.spec_from_file_location("smoke", ROOT / ".github" / "scripts" / "zathroth-smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HOST = server_address()
    return module


def server_address():
    """The address the game listens on: ZATHROTH_BIND_IP, else ZATHROTH_SERVER_IP, from .env."""
    settings = {}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, _, value = line.partition("=")
            settings[key.strip()] = value.strip().strip('"')
    return os.environ.get("ZATHROTH_LOADTEST_HOST") or settings.get("ZATHROTH_BIND_IP") or settings.get("ZATHROTH_SERVER_IP") or "127.0.0.1"


def connect():
    db = sqlite3.connect(DATABASE, timeout=30)
    db.execute("PRAGMA foreign_keys = ON")
    return db


def character_name(index):
    letters = "abcdefghijklmnopqrstuvwxyz"
    return CHARACTER_PREFIX + letters[index // 26].upper() + letters[index % 26]


def remove_test_accounts(wait_seconds=60):
    """Deletes every loadtest account once none of its characters is online."""
    deadline = time.monotonic() + wait_seconds
    with connect() as db:
        while True:
            online = db.execute(
                "SELECT count(*) FROM players_online o JOIN players p ON p.id = o.player_id "
                "JOIN accounts a ON a.id = p.account_id WHERE a.name LIKE ?",
                (ACCOUNT_PREFIX + "%",),
            ).fetchone()[0]
            if not online or time.monotonic() > deadline:
                break
            time.sleep(1)
        if online:
            print(f"{online} test characters are still online; their accounts were left in place. Run the test again to clean up.")
            return 0
        time.sleep(3)  # let the game finish saving the last logouts
        removed = db.execute("DELETE FROM accounts WHERE name LIKE ?", (ACCOUNT_PREFIX + "%",)).rowcount
    return removed


def create_test_accounts(count):
    password = secrets.token_urlsafe(18)
    password_hash = hashlib.sha1(password.encode()).hexdigest()
    with connect() as db:
        towns = [row[0] for row in db.execute("SELECT id FROM towns WHERE posx > 0 AND id >= ? ORDER BY id", (FIRST_MAIN_TOWN,))]
        if not towns:
            raise SystemExit("No towns found. Start the game server once before running a load test.")
        bots = []
        for index in range(count):
            account = f"{ACCOUNT_PREFIX}{index + 1:03d}"
            name = character_name(index)
            vocation = VOCATIONS[index % len(VOCATIONS)]
            sex = index % 2
            account_id = db.execute(
                "INSERT INTO accounts (name, email, password, creation) VALUES (?, '', ?, ?) RETURNING id",
                (account, password_hash, int(time.time())),
            ).fetchone()[0]
            # Position 0,0,0 makes the game place the character at its town's temple.
            db.execute(
                """
                INSERT INTO players (
                    name, account_id, level, vocation, experience, health, healthmax, mana, manamax,
                    soul, cap, town_id, posx, posy, posz, conditions, sex, looktype, lookhead, lookbody, looklegs, lookfeet
                ) VALUES (?, ?, 8, ?, 4200, 185, 185, 90, 90, 100, 470, ?, 0, 0, 0, X'', ?, ?, 78, 106, 116, 95)
                """,
                (name, account_id, vocation, towns[index % len(towns)], sex, 128 if sex else 136),
            )
            bots.append((account, name))
    return bots, password, len(towns)


class Bot(threading.Thread):
    def __init__(self, client, session, name, stop):
        super().__init__(daemon=True)
        self.game = client.GameClient(session, name)
        self.name_ = name
        self.stop = stop
        self.error = None

    def run(self):
        self.game.sock.settimeout(1)
        next_ping = time.monotonic()
        try:
            while not self.stop.is_set():
                if time.monotonic() >= next_ping:
                    self.game.send(b"\x1e")
                    next_ping = time.monotonic() + PING_EVERY
                try:
                    if not self.game.sock.recv(65536):
                        raise ConnectionError("the server closed the connection")
                except socket.timeout:
                    pass
        except (OSError, ConnectionError) as error:
            self.error = str(error)
        finally:
            try:
                self.game.close()
            except OSError:
                pass


def game_usage():
    try:
        line = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}} CPU {{.CPUPerc}} memory {{.MemUsage}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        return "; ".join(part for part in line.splitlines() if "zathroth" in part) or "not available"
    except (OSError, subprocess.SubprocessError):
        return "not available"


def say(*parts):
    """Prints, but never fails: after the SSH window closes the cleanup must still run."""
    try:
        print(*parts, flush=True)
    except OSError:
        pass


def interrupted(signum, frame):
    raise KeyboardInterrupt


def login(client, account, password):
    """HTTP login; waits out the service's limit of 30 logins per address per minute."""
    deadline = time.monotonic() + 90
    while True:
        reply = client.http_login(account, password)
        if "session" in reply:
            return reply["session"]["sessionkey"]
        message = reply.get("errorMessage", "no session in the reply")
        if "Too many attempts" not in message or time.monotonic() > deadline:
            raise RuntimeError(message)
        time.sleep(5)


def players_record():
    with connect() as db:
        row = db.execute("SELECT value FROM server_config WHERE config = 'players_record'").fetchone()
    return int(row[0]) if row else None


def restore_players_record(saved):
    """Puts back the record the bots raised; the game reloads it from here when it restarts."""
    if saved is None:
        return
    with connect() as db:
        db.execute("UPDATE server_config SET value = ? WHERE config = 'players_record' AND CAST(value AS INTEGER) > ?", (str(saved), saved))


def main():
    # Ctrl+C, kill and closing the SSH window all stop the test early and still clean up,
    # even when the shell started this with SIGINT ignored.
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, interrupted)
    if sys.argv[1:] == ["clean"]:
        say(f"Removed {remove_test_accounts(wait_seconds=5)} test accounts.")
        return
    if len(sys.argv) != 3 or not all(arg.isdigit() for arg in sys.argv[1:]):
        raise SystemExit(__doc__)
    count, seconds = int(sys.argv[1]), int(sys.argv[2])
    if not 1 <= count <= MAX_BOTS or not 10 <= seconds <= MAX_SECONDS:
        raise SystemExit(f"Use 1-{MAX_BOTS} bots and 10-{MAX_SECONDS} seconds.")
    if not DATABASE.exists():
        raise SystemExit(f"{DATABASE} not found. Run this from the server's repository folder.")

    leftovers = remove_test_accounts(wait_seconds=5)
    if leftovers:
        say(f"Removed {leftovers} test accounts left from an earlier run.")
    record = players_record()
    client = load_client()
    say(f"Server {client.HOST}: usage before the test: {game_usage()}")
    bots, password, town_count = create_test_accounts(count)
    say(f"Created {count} test accounts in {town_count} towns. Logging in: the login service allows 30 logins "
        f"per address per minute, so this takes about {max(count * 0.6, (count - 1) // 30 * 60):.0f} s...")

    stop = threading.Event()
    running, failures, times = [], [], []
    try:
        for account, name in bots:
            started = time.monotonic()
            for attempt in range(3):
                try:
                    bot = Bot(client, login(client, account, password), name, stop)
                    bot.start()
                    running.append(bot)
                    times.append(time.monotonic() - started)
                    break
                except (OSError, ConnectionError) as error:
                    # The game briefly refuses an address that connects very often; try again.
                    if attempt == 2:
                        failures.append(f"{name}: {error}")
                    time.sleep(4)
                except Exception as error:  # report every other failed login and keep going
                    failures.append(f"{name}: {error}")
                    break
        if times:
            say(f"{len(running)} of {count} bots online. Login time: average {sum(times) / len(times):.2f} s, slowest {max(times):.2f} s (including waits for the login limit).")
        for failure in failures[:10]:
            say("  login failed:", failure)

        end = time.monotonic() + seconds
        halfway_reported = False
        while time.monotonic() < end:
            time.sleep(1)
            if not halfway_reported and time.monotonic() > end - seconds / 2:
                say(f"Halfway, {sum(bot.is_alive() for bot in running)} bots connected. Server usage: {game_usage()}")
                halfway_reported = True
        dropped = [bot for bot in running if bot.error]
        say(f"Time is up: {len(running) - len(dropped)} of {len(running)} bots stayed connected for {seconds} s.")
        for bot in dropped[:10]:
            say(f"  {bot.name_} dropped: {bot.error}")
    except KeyboardInterrupt:
        say("Stopped early.")
    finally:
        # The cleanup must finish, so a second Ctrl+C cannot cut it short.
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, signal.SIG_IGN)
        stop.set()
        for bot in running:
            bot.join(timeout=5)
        removed = remove_test_accounts()
        restore_players_record(record)
        say(f"Logged out and removed {removed} test accounts. Player record restored to {record}.")


if __name__ == "__main__":
    main()
