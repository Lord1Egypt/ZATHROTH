"""Offline checks using the real SQLite schema; never connects to the game."""

from contextlib import ExitStack
import os
from pathlib import Path
import signal
import socket
import sqlite3
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import loadtest2 as tool


class Loadtest2Tests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = self.stack.enter_context(tempfile.TemporaryDirectory())
        path = Path(folder) / "game.sqlite3"
        self.stack.enter_context(patch.object(tool, "DATABASE", path))
        self.stack.enter_context(patch.object(tool, "SETTLE_SECONDS", 0))
        self.stack.enter_context(patch.object(tool, "POLL_SECONDS", 0.01))
        self.stack.enter_context(patch.object(tool, "say"))
        with sqlite3.connect(path) as db:
            db.executescript((tool.ROOT / "schema.sql").read_text())
            db.executemany("INSERT INTO towns (id, name, posx, posy, posz) VALUES (?, ?, 100, 100, 7)",
                           [(i, f"Town {i}") for i in range(1, 31)])
            db.execute("INSERT INTO accounts (name, password) VALUES ('realowner', 'secret')")
            db.execute("INSERT INTO players (name, account_id) VALUES ('Real Player', 1)")

    def test_population_and_cleanup_preserve_record_and_real_players(self):
        bots, _, towns = tool.create_accounts(200, threading.Event())
        self.assertEqual(towns, 26)
        self.assertEqual(len(bots), 200)
        with tool.database() as db:
            players = db.execute("SELECT name, level, experience, looktype, sex, town_id, vocation, posx, posy, posz, comment FROM players WHERE account_id <> 1").fetchall()
            self.assertEqual(len({p[0].casefold() for p in players}), 200)
            self.assertEqual(len({p[1] for p in players}), 200)
            self.assertEqual(len({p[5] for p in players}), 26)
            self.assertEqual({p[6] for p in players}, set(tool.VOCATIONS))
            self.assertGreater(len({p[3] for p in players}), 10)
            for name, level, experience, _, _, _, _, x, y, z, comment in players:
                self.assertRegex(name, r"^[A-Z][a-z]+ [A-Z][a-z]+$")
                self.assertNotIn("test", name.lower())
                self.assertTrue(8 <= level <= 1000)
                expected = (50 * level ** 3 - 300 * level ** 2 + 850 * level - 600) // 3
                self.assertEqual(experience, expected)
                self.assertEqual((x, y, z), (0, 0, 0))
                self.assertEqual(comment, tool.OWNER_COMMENT)
            for account, name, _ in bots:
                self.assertEqual(account, name.replace(" ", "").lower())
            db.execute("UPDATE server_config SET value = '201' WHERE config = 'players_record'")
        self.assertEqual(tool.remove_accounts(0), 200)
        self.assertEqual(tool.remove_accounts(0), 0)
        with tool.database() as db:
            self.assertEqual(db.execute("SELECT name FROM players").fetchall(), [("Real Player",)])
            self.assertEqual(db.execute("SELECT value FROM server_config WHERE config = 'players_record'").fetchone(), ("201",))
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_existing_character_and_account_name_collisions_are_skipped(self):
        # With shuffle disabled these are the first candidates popped for each sex.
        first_name = tool.FIRST_NAMES[0][-1]
        surname = tool.LAST_NAMES[-1]
        other = (tool.FIRST_NAMES[1][-1] + surname).lower()
        with tool.database() as db:
            db.execute("UPDATE players SET name = ? WHERE id = 1", (f"{first_name} {surname}",))
            db.execute("UPDATE accounts SET name = ? WHERE id = 1", (other,))
        with patch.object(tool.RANDOM, "shuffle", lambda names: None):
            bots, _, _ = tool.create_accounts(2, threading.Event())
        self.assertNotIn(f"{first_name} {surname}", [b[1] for b in bots])
        self.assertNotIn(other, [b[0] for b in bots])

    def test_cleanup_requires_both_tags_and_all_characters_owned(self):
        bots, _, _ = tool.create_accounts(3, threading.Event())
        with tool.database() as db:
            db.execute("UPDATE accounts SET email = ? WHERE id = 1", (tool.OWNER_EMAIL,))
            db.execute("UPDATE players SET comment = '' WHERE id = ?", (bots[0][2],))
            account_id = db.execute("SELECT account_id FROM players WHERE id = ?", (bots[1][2],)).fetchone()[0]
            db.execute("INSERT INTO players (name, account_id) VALUES ('Other Character', ?)", (account_id,))
        self.assertEqual(tool.remove_accounts(0), 1)
        with tool.database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 3)

    def test_online_accounts_are_never_deleted(self):
        bots, _, _ = tool.create_accounts(1, threading.Event())
        with tool.database() as db:
            db.execute("INSERT INTO players_online (player_id) VALUES (?)", (bots[0][2],))
        with self.assertRaisesRegex(RuntimeError, "still online"):
            tool.remove_accounts(0)
        with tool.database() as db:
            self.assertEqual(len(tool.owned_accounts(db)), 1)

    def test_cancelled_creation_rolls_back_and_lock_refuses_second_run(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(InterruptedError):
            tool.create_accounts(2, stop)
        with tool.database() as db:
            self.assertEqual(tool.owned_accounts(db), [])
        with tool.run_lock():
            with self.assertRaisesRegex(SystemExit, "already running"):
                with tool.run_lock():
                    self.fail("Second invocation acquired the lock")

    def test_login_retries_limits_and_surfaces_real_failure(self):
        client = types.SimpleNamespace()
        client.http_login = unittest.mock.Mock(side_effect=[
            {"errorMessage": "Too many attempts. Try later."}, {"session": {"sessionkey": "token"}},
        ])
        stop = unittest.mock.Mock()
        stop.is_set.return_value = False
        self.assertEqual(tool.login(client, "account", "password", stop), "token")
        stop.wait.assert_called_once_with(5)
        client.http_login.return_value = {"errorMessage": "Account is disabled"}
        client.http_login.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "Account is disabled"):
            tool.login(client, "account", "password", stop)

    def test_failed_handshake_closes_partial_socket(self):
        sock = unittest.mock.Mock()

        class FailedClient:
            def __init__(self, session, name):
                self.sock = sock
                raise ConnectionError("Handshake failed")

        with self.assertRaisesRegex(ConnectionError, "Handshake failed"):
            tool.Bot(types.SimpleNamespace(GameClient=FailedClient), "session", "Someone Vale")
        sock.close.assert_called_once()

    def test_keepalive_and_turns_continue_beyond_idle_limit(self):
        now = [0]
        sent = []

        class FakeSocket:
            def settimeout(self, seconds):
                pass

            def recv(self, count):
                now[0] += 1
                if now[0] >= 1000:
                    bot.stop.set()
                return b"traffic"

            def close(self):
                pass

        class FakeClient:
            def __init__(self, session, name):
                self.sock = FakeSocket()

            def send(self, payload):
                sent.append((now[0], payload))

            def close(self):
                pass

        bot = tool.Bot(types.SimpleNamespace(GameClient=FakeClient), "session", "Someone Vale")
        with patch.object(tool.time, "monotonic", side_effect=lambda: now[0]):
            bot.run()
        pings = [stamp for stamp, payload in sent if payload == b"\x1e"]
        turns = [stamp for stamp, payload in sent if payload in (b"\x6f", b"\x70", b"\x71", b"\x72")]
        self.assertGreater(pings[-1], 900)
        self.assertGreater(turns[-1], 900)
        self.assertLessEqual(max(b - a for a, b in zip(pings, pings[1:])), 10)
        self.assertLessEqual(max(b - a for a, b in zip(turns, turns[1:])), 60)

    def test_signals_logout_cleanup_and_keep_increased_record(self):
        # Socket pairs exercise the actual bot thread, ping/turn loop and logout.
        # Only the game handshake is replaced; SQL and OS signal handling are real.
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum):
                sent = []
                peers = []
                timers = []
                before = signal.getsignal(signum)

                class FakeGameClient:
                    def __init__(self, session, name):
                        self.sock, peer = socket.socketpair()
                        peers.append(peer)
                        with tool.database() as db:
                            self.player_id = db.execute("SELECT id FROM players WHERE name = ?", (name,)).fetchone()[0]
                            db.execute("INSERT INTO players_online (player_id) VALUES (?)", (self.player_id,))
                            db.execute("UPDATE server_config SET value = '101' WHERE config = 'players_record'")
                        timer = threading.Timer(0.15, lambda: os.kill(os.getpid(), signum))
                        timers.append(timer)
                        timer.start()

                    def send(self, payload):
                        sent.append(payload)

                    def close(self):
                        self.send(b"\x14")
                        self.sock.close()
                        with tool.database() as db:
                            db.execute("DELETE FROM players_online WHERE player_id = ?", (self.player_id,))

                client = types.SimpleNamespace(HOST="offline", GameClient=FakeGameClient,
                                               http_login=lambda account, password: {"session": {"sessionkey": "key"}})
                try:
                    with patch.object(tool, "load_client", return_value=client), patch.object(tool, "game_usage", return_value="offline"):
                        tool.main(["1"])
                finally:
                    for timer in timers:
                        timer.cancel()
                        timer.join()
                    for peer in peers:
                        peer.close()
                self.assertEqual(signal.getsignal(signum), before)
                self.assertIn(b"\x1e", sent)
                self.assertIn(b"\x6f", sent)
                self.assertIn(b"\x14", sent)
                with tool.database() as db:
                    self.assertEqual(tool.owned_accounts(db), [])
                    self.assertEqual(db.execute("SELECT value FROM server_config WHERE config = 'players_record'").fetchone()[0], "101")


if __name__ == "__main__":
    unittest.main()
