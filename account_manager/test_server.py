"""Exercise the browser and game login against the actual SQLite schema."""

import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from server import AccountServer, ROOT
from storage import Accounts


class Browser:
    def __init__(self, base):
        self.base = base
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = ""

    def request(self, route, data=None, headers=None):
        request = Request(self.base + route, data=data, headers=headers or {})
        try:
            with self.opener.open(request, timeout=5) as response:
                status, body = response.status, response.read().decode()
        except HTTPError as error:
            with error:
                status, body = error.code, error.read().decode()
        if match := re.search(r'name="csrf" value="([0-9a-f]+)"', body):
            self.csrf = match[1]
        return status, body

    def form(self, action, **fields):
        values = {"action": action, "csrf": self.csrf, **fields}
        return self.request("/manage", urlencode(values).encode())

    def game(self, identifier, password):
        payload = json.dumps({"type": "login", "email": identifier, "password": password}).encode()
        status, body = self.request("/login", payload, {"Content-Type": "application/json"})
        return status, json.loads(body)

    def game_status(self, action):
        payload = json.dumps({"type": action}).encode()
        status, body = self.request("/login", payload, {"Content-Type": "application/json"})
        return status, json.loads(body)


class AccountManagerTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / "test.sqlite3"
        with sqlite3.connect(self.db_path) as db:
            db.executescript((ROOT / "schema.sql").read_text())
        accounts = Accounts(self.db_path, 0, ROOT / "data/XML/vocations.xml")
        self.server = AccountServer(("127.0.0.1", 0), accounts, "192.168.1.104", 7172, 8088)
        worker = Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.browser = Browser(self.base)

    def game_startup(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO towns (id, name, posx, posy, posz) VALUES (1, 'Temple', 100, 100, 7)")

    def register(self, browser, name, email):
        self.assertEqual(browser.request("/")[0], 200)
        self.assertIn("Create an account", browser.form("signin", identifier="1", password="1")[1])
        status, body = browser.form("register", name=name, email=email, password="Adventure pass", confirm="Adventure pass")
        self.assertEqual(status, 200, body)
        self.assertIn("Account created", body)

    def test_account_character_and_game_login(self):
        self.assertEqual(self.browser.request("/health")[0], 503)
        self.game_startup()
        self.assertEqual(self.browser.request("/health")[0], 200)
        self.assertIn("192.168.1.104:8088", self.browser.game("1", "1")[1]["errorMessage"])
        self.register(self.browser, "adventurer", "adventurer@example.test")
        self.assertIn("Create a character", self.browser.game("adventurer", "Adventure pass")[1]["errorMessage"])
        self.assertIn("Character created", self.browser.form("character", name="Arden Fox", sex="0", vocation="9")[1])
        status, game = self.browser.game("ADVENTURER@EXAMPLE.TEST", "Adventure pass")
        self.assertEqual(status, 200)
        self.assertEqual(game["playdata"]["worlds"][0]["externaladdressprotected"], "192.168.1.104")
        self.assertEqual(game["playdata"]["worlds"][0]["externalportprotected"], 7172)
        self.assertEqual(game["playdata"]["worlds"][0]["pvptype"], 3)
        arden = game["playdata"]["characters"][0]
        self.assertEqual((arden["name"], arden["level"], arden["vocation"], arden["outfitid"]), ("Arden Fox", 8, "Monk", 136))

        digest = hashlib.sha256(game["session"]["sessionkey"].encode()).hexdigest()
        with sqlite3.connect(self.db_path) as db:
            session = db.execute("SELECT account_id FROM account_sessions WHERE id = ?", (digest,)).fetchone()
            account_id, town_id, condition_type = db.execute("SELECT account_id, town_id, typeof(conditions) FROM players").fetchone()
            self.assertEqual((session, town_id, condition_type), ((account_id,), 1, "blob"))
            db.execute("INSERT INTO players_online (player_id) VALUES (?)", (arden["characterid"],))

        self.assertEqual(self.browser.game_status("cacheinfo")[1]["playersonline"], 1)
        self.assertIn("creatureraceid", self.browser.game_status("boostedcreature")[1])
        self.assertIsInstance(self.browser.game_status("eventschedule")[1]["eventlist"], list)
        self.assertEqual(self.browser.form("delete", character=arden["characterid"])[0], 400)
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM players_online")
        self.assertIn("scheduled for deletion", self.browser.form("delete", character=arden["characterid"])[1])
        self.assertIn("Create a character", self.browser.game("adventurer", "Adventure pass")[1]["errorMessage"])
        self.assertIn("Character restored", self.browser.form("restore", character=arden["characterid"])[1])

        old_browser = Browser(self.base)
        old_browser.request("/")
        old_browser.form("signin", identifier="adventurer", password="Adventure pass")
        self.assertIn("Password changed", self.browser.form("password", current="Adventure pass", password="New adventure", confirm="New adventure")[1])
        self.assertIn("Sign in", old_browser.request("/")[1])
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM account_sessions").fetchone(), (0,))
        self.assertEqual(self.browser.game("adventurer", "Adventure pass")[1]["errorCode"], 3)
        self.assertIn("session", self.browser.game("adventurer", "New adventure")[1])

    def test_csrf_duplicate_names_and_ownership(self):
        self.game_startup()
        self.assertEqual(self.browser.form("signin", identifier="1", password="1")[0], 400)
        self.assertEqual(self.browser.form("register", name="anonymous", email="anonymous@example.test", password="Adventure pass", confirm="Adventure pass")[0], 400)
        self.register(self.browser, "adventurer", "adventurer@example.test")
        self.browser.form("character", name="Arden Fox", sex="0", vocation="1")
        character = self.browser.game("adventurer", "Adventure pass")[1]["playdata"]["characters"][0]

        other = Browser(self.base)
        other.request("/")
        other.form("signin", identifier="1", password="1")
        self.assertIn("already registered", other.form("register", name="Another", email="ADVENTURER@EXAMPLE.TEST", password="Adventure pass", confirm="Adventure pass")[1])
        self.assertEqual(other.form("register", name="Another", email="another@example.test", password="Adventure pass", confirm="Adventure pass")[0], 200)
        self.assertIn("already in use", other.form("character", name="arden fox", sex="1", vocation="2")[1])
        self.assertEqual(other.form("delete", character=character["characterid"])[0], 400)
        self.assertEqual(self.browser.game("adventurer", "Adventure pass")[1]["playdata"]["characters"][0]["name"], "Arden Fox")


@unittest.skipUnless(os.getenv("ZATHROTH_TEST_URL"), "set ZATHROTH_TEST_URL for the read-only live smoke")
class LiveAccountManagerTest(unittest.TestCase):
    def test_running_service(self):
        browser = Browser(os.environ["ZATHROTH_TEST_URL"].rstrip("/"))
        status, body = browser.request("/health")
        self.assertEqual(status, 200, body)
        self.assertTrue(json.loads(body)["ready"])
        self.assertEqual(browser.request("/")[0], 200)
        self.assertIn("Create an account", browser.form("signin", identifier="1", password="1")[1])
        self.assertIn("in your browser", browser.game("1", "1")[1]["errorMessage"])
        self.assertIn("playersonline", browser.game_status("cacheinfo")[1])


if __name__ == "__main__":
    unittest.main()
