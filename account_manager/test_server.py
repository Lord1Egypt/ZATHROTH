"""Exercise the browser and game login against the actual SQLite schema."""

import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

import guard
import server as account_server
from server import AccountServer, ROOT
from storage import MANAGER_NAME, Accounts


class Browser:
    def __init__(self, base, headers=None):
        self.base = base
        self.headers = headers or {}
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = ""
        self.response_headers = {}

    def request(self, route, data=None, headers=None):
        request = Request(self.base + route, data=data, headers={**self.headers, **(headers or {})})
        try:
            with self.opener.open(request, timeout=20) as response:
                status, body = response.status, response.read().decode()
                self.response_headers = response.headers
        except HTTPError as error:
            with error:
                status, body = error.code, error.read().decode()
                self.response_headers = error.headers
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
        self.server = AccountServer(("127.0.0.1", 0), accounts, "192.168.1.104", 7172)
        worker = Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.browser = Browser(self.base)

    def game_startup(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO towns (id, name, posx, posy, posz) VALUES (1, 'Temple', 100, 100, 7)")

    def solve(self, page):
        """The CAPTCHA fields that answer the challenge shown on `page`."""
        token = re.search(r'name="captcha_id" value="([0-9a-f]+)"', page)[1]
        return {"captcha_id": token, "captcha": self.server.captchas.pending[token][0]}

    def register(self, browser, name, email):
        self.assertEqual(browser.request("/")[0], 200)
        page = browser.form("signin", identifier="1", password="1")[1]
        self.assertIn("Create an account", page)
        status, body = browser.form("register", name=name, email=email, password="Adventure pass", confirm="Adventure pass", **self.solve(page))
        self.assertEqual(status, 200, body)
        self.assertIn("Account created", body)

    def names(self, game):
        return [character["name"] for character in game["playdata"]["characters"]]

    def test_shared_account_manager_login(self):
        self.assertIn("still starting", self.browser.game("1", "1")[1]["errorMessage"])
        self.game_startup()
        for attempt in range(2):
            status, game = self.browser.game("1", "1")
            self.assertEqual(status, 200)
            self.assertEqual(self.names(game), [MANAGER_NAME])
        digest = hashlib.sha256(game["session"]["sessionkey"].encode()).hexdigest()
        with sqlite3.connect(self.db_path) as db:
            manager = db.execute(
                "SELECT a.name, a.password, p.level FROM players p JOIN accounts a ON a.id = p.account_id WHERE p.name = ?",
                (MANAGER_NAME,),
            ).fetchall()
            self.assertEqual(manager, [("1", "", 1)])
            session = db.execute("SELECT a.name FROM account_sessions s JOIN accounts a ON a.id = s.account_id WHERE s.id = ?", (digest,)).fetchone()
            self.assertEqual(session, ("1",))
            # An account made in game has no email; an empty identifier must not reach it.
            db.execute("UPDATE accounts SET password = ? WHERE name = '1'", (hashlib.sha1(b"Adventure pass").hexdigest(),))
        self.assertEqual(self.browser.game("", "Adventure pass")[1]["errorCode"], 3)
        self.assertEqual(self.browser.game(" ", "Adventure pass")[1]["errorCode"], 3)

    def test_account_character_and_game_login(self):
        self.assertEqual(self.browser.request("/health")[0], 503)
        self.game_startup()
        self.assertEqual(self.browser.request("/health")[0], 200)
        self.register(self.browser, "adventurer", "adventurer@example.test")
        self.assertEqual(self.names(self.browser.game("adventurer", "Adventure pass")[1]), [MANAGER_NAME])
        self.assertIn("Character created", self.browser.form("character", name="Arden Fox", sex="0", vocation="9")[1])
        status, game = self.browser.game("ADVENTURER@EXAMPLE.TEST", "Adventure pass")
        self.assertEqual(status, 200)
        self.assertEqual(game["playdata"]["worlds"][0]["externaladdressprotected"], "192.168.1.104")
        self.assertEqual(game["playdata"]["worlds"][0]["externalportprotected"], 7172)
        self.assertEqual(game["playdata"]["worlds"][0]["pvptype"], 3)
        self.assertEqual(self.names(game), ["Arden Fox", MANAGER_NAME])
        arden = game["playdata"]["characters"][0]
        self.assertEqual((arden["name"], arden["level"], arden["vocation"], arden["outfitid"]), ("Arden Fox", 8, "Monk", 136))

        digest = hashlib.sha256(game["session"]["sessionkey"].encode()).hexdigest()
        with sqlite3.connect(self.db_path) as db:
            session = db.execute("SELECT account_id FROM account_sessions WHERE id = ?", (digest,)).fetchone()
            account_id, town_id, condition_type = db.execute("SELECT account_id, town_id, typeof(conditions) FROM players WHERE name = 'Arden Fox'").fetchone()
            self.assertEqual((session, town_id, condition_type), ((account_id,), 1, "blob"))
            db.execute("INSERT INTO players_online (player_id) VALUES (?)", (arden["characterid"],))

        self.assertEqual(self.browser.game_status("cacheinfo")[1]["playersonline"], 1)
        self.assertIn("creatureraceid", self.browser.game_status("boostedcreature")[1])
        self.assertIsInstance(self.browser.game_status("eventschedule")[1]["eventlist"], list)
        self.assertEqual(self.browser.form("delete", character=arden["characterid"])[0], 400)
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM players_online")
        self.assertIn("scheduled for deletion", self.browser.form("delete", character=arden["characterid"])[1])
        self.assertEqual(self.names(self.browser.game("adventurer", "Adventure pass")[1]), [MANAGER_NAME])
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
        page = other.form("signin", identifier="1", password="1")[1]
        body = other.form("register", name="Another", email="ADVENTURER@EXAMPLE.TEST", password="Adventure pass", confirm="Adventure pass", **self.solve(page))[1]
        self.assertIn("already registered", body)
        self.assertEqual(other.form("register", name="Another", email="another@example.test", password="Adventure pass", confirm="Adventure pass", **self.solve(body))[0], 200)
        self.assertIn("already in use", other.form("character", name="arden fox", sex="1", vocation="2")[1])
        self.assertEqual(other.form("delete", character=character["characterid"])[0], 400)
        self.assertEqual(self.browser.game("adventurer", "Adventure pass")[1]["playdata"]["characters"][0]["name"], "Arden Fox")

    def guest_page(self, browser=None):
        browser = browser or self.browser
        browser.request("/")
        return browser.form("signin", identifier="1", password="1")[1]

    def test_registration_needs_the_captcha(self):
        self.game_startup()
        page = self.guest_page()
        self.assertIn('name="captcha_id"', page)
        self.assertNotIn("<text", page)
        fields = dict(name="newplayer", email="new@example.test", password="Adventure pass", confirm="Adventure pass")

        status, body = self.browser.form("register", **fields)
        self.assertEqual(status, 400)
        self.assertIn("characters did not match", body)

        solved = self.solve(body)
        status, body = self.browser.form("register", **fields, captcha_id=solved["captcha_id"], captcha="WRONG")
        self.assertEqual(status, 400)
        self.assertIn("characters did not match", body)
        self.assertNotIn(solved["captcha_id"], body)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM accounts WHERE name = 'newplayer'").fetchone(), (0,))

        # A used challenge cannot be answered again, even correctly.
        status, body = self.browser.form("register", **fields, **solved)
        self.assertEqual(status, 400)
        status, body = self.browser.form("register", **fields, **self.solve(body))
        self.assertEqual(status, 200, body)
        self.assertIn("Account created", body)

    def test_sign_in_asks_for_a_captcha_after_failures(self):
        self.game_startup()
        self.register(self.browser, "adventurer", "adventurer@example.test")
        other = Browser(self.base)
        other.request("/")
        for _ in range(guard.IP_CAPTCHA_AFTER):
            self.assertNotIn("captcha_id", other.request("/")[1])
            status, body = other.form("signin", identifier="adventurer", password="wrong password")
            self.assertEqual(status, 400)
        self.assertIn("captcha_id", body)

        status, body = other.form("signin", identifier="adventurer", password="Adventure pass")
        self.assertEqual(status, 400)
        self.assertIn("characters did not match", body)
        status, body = other.form("signin", identifier="adventurer", password="Adventure pass", **self.solve(body))
        self.assertEqual(status, 200)
        self.assertIn("adventurer", body)

    def test_repeated_failures_block_game_and_browser_logins(self):
        self.game_startup()
        self.register(self.browser, "adventurer", "adventurer@example.test")
        for _ in range(guard.IP_BLOCK_AFTER):
            self.assertEqual(self.browser.game("adventurer", "wrong password")[1]["errorCode"], 3)
        status, game = self.browser.game("adventurer", "Adventure pass")
        self.assertEqual(game["errorCode"], 2)
        self.assertIn("Too many failed attempts", game["errorMessage"])

        other = Browser(self.base)
        other.request("/")
        status, body = other.form("signin", identifier="adventurer", password="Adventure pass")
        self.assertEqual(status, 400)
        self.assertIn("Too many failed attempts", body)
        # The shared 1/1 login is not a guess and stays available.
        self.assertEqual(self.browser.game("1", "1")[1]["playdata"]["characters"][0]["name"], MANAGER_NAME)

    def test_new_accounts_are_limited_per_address(self):
        self.game_startup()
        for index in range(guard.REGISTRATIONS_PER_IP):
            browser = Browser(self.base)
            page = self.guest_page(browser)
            status, body = browser.form("register", name=f"player{index}", email=f"p{index}@example.test", password="Adventure pass", confirm="Adventure pass", **self.solve(page))
            self.assertEqual(status, 200, body)
        browser = Browser(self.base)
        page = self.guest_page(browser)
        status, body = browser.form("register", name="onemore", email="more@example.test", password="Adventure pass", confirm="Adventure pass", **self.solve(page))
        self.assertEqual(status, 400)
        self.assertIn("Too many accounts", body)

    def test_common_passwords_are_refused(self):
        self.game_startup()
        page = self.guest_page()
        for password in ("password123", "aaaaaaaaaa", "xxadventurerxx"):
            status, body = self.browser.form("register", name="adventurer", email="a@example.test", password=password, confirm=password, **self.solve(page))
            self.assertEqual(status, 400, password)
            self.assertIn("harder to guess", body)
            page = body

    def test_only_wrong_passwords_count_as_failures(self):
        self.game_startup()
        self.register(self.browser, "adventurer", "adventurer@example.test")
        for _ in range(guard.IP_BLOCK_AFTER + 2):
            status, body = self.browser.form("password", current="Adventure pass", password="password123", confirm="password123")
            self.assertEqual(status, 400)
            self.assertIn("harder to guess", body)
        status, body = self.browser.form("password", current="Adventure pass", password="Another long pass", confirm="Another long pass")
        self.assertEqual(status, 200, body)
        self.assertIn("Password changed", body)

    def second_server(self, **options):
        accounts = Accounts(self.db_path, 0, ROOT / "data/XML/vocations.xml")
        server = AccountServer(("127.0.0.1", 0), accounts, "192.168.1.104", 7172, **options)
        Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, f"http://127.0.0.1:{server.server_port}"

    def test_a_trusted_proxy_identifies_visitors_and_marks_cookies_secure(self):
        self.game_startup()
        server, base = self.second_server(trusted_proxy="127.0.0.1")
        server.accounts.register("adventurer", "adventurer@example.test", "Adventure pass")
        https = {"X-Forwarded-Proto": "https"}
        victim = Browser(base, {"X-Forwarded-For": "203.0.113.5", **https})
        other = Browser(base, {"X-Forwarded-For": "203.0.113.6", **https})

        victim.request("/")
        self.assertIn("Secure", victim.response_headers["Set-Cookie"])
        plain = Browser(base, {"X-Forwarded-For": "203.0.113.7"})
        plain.request("/")
        self.assertNotIn("Secure", plain.response_headers["Set-Cookie"])

        for _ in range(guard.IP_BLOCK_AFTER):
            victim.game("adventurer", "wrong password")
        self.assertEqual(victim.game("adventurer", "Adventure pass")[1]["errorCode"], 2)
        self.assertIn("session", other.game("adventurer", "Adventure pass")[1])

        garbled = Browser(base, {"X-Forwarded-For": "not an address"})
        self.assertIn("session", garbled.game("adventurer", "Adventure pass")[1])

    def test_home_network_clients_get_the_lan_game_address(self):
        self.game_startup()
        server, base = self.second_server(trusted_proxy="127.0.0.1", lan_host="192.168.1.104")
        server.accounts.register("adventurer", "adventurer@example.test", "Adventure pass")
        server.world["externaladdressprotected"] = server.world["externaladdressunprotected"] = "zathroth.example.test"

        def address(headers):
            world = Browser(base, headers).game("adventurer", "Adventure pass")[1]["playdata"]["worlds"][0]
            self.assertEqual(world["externaladdressprotected"], world["externaladdressunprotected"])
            return world["externaladdressprotected"]

        self.assertEqual(address({"X-Forwarded-For": "8.8.8.8"}), "zathroth.example.test")
        self.assertEqual(address({"X-Forwarded-For": "192.168.1.50"}), "192.168.1.104")
        self.assertEqual(address({}), "192.168.1.104")

    def test_a_proxy_host_name_is_resolved_in_the_background(self):
        server, _ = self.second_server(trusted_proxy="localhost")
        for _ in range(50):
            if server.proxy_addresses:
                break
            time.sleep(0.1)
        self.assertEqual(server.proxy_addresses, {"127.0.0.1"})
        self.assertTrue(server.is_trusted_proxy("127.0.0.1"))
        self.assertFalse(server.is_trusted_proxy("203.0.113.5"))

    def test_a_proxy_name_that_does_not_resolve_never_slows_requests(self):
        self.game_startup()
        # The lookup of this name runs in the background; requests do not wait for it.
        server, base = self.second_server(trusted_proxy="proxy.invalid")
        started = time.monotonic()
        self.assertEqual(Browser(base).request("/")[0], 200)
        self.assertLess(time.monotonic() - started, 5)
        self.assertFalse(server.is_trusted_proxy("127.0.0.1"))

    def test_forwarded_headers_from_anyone_else_are_ignored(self):
        self.game_startup()
        self.register(self.browser, "adventurer", "adventurer@example.test")
        spoof = Browser(self.base, {"X-Forwarded-For": "203.0.113.5", "X-Forwarded-Proto": "https"})
        spoof.request("/")
        self.assertNotIn("Secure", spoof.response_headers["Set-Cookie"])
        for index in range(guard.IP_BLOCK_AFTER):
            spoof.headers["X-Forwarded-For"] = f"203.0.113.{index + 10}"
            spoof.game("adventurer", "wrong password")
        spoof.headers["X-Forwarded-For"] = "198.51.100.99"
        self.assertEqual(spoof.game("adventurer", "Adventure pass")[1]["errorCode"], 2)

    def test_idle_and_slow_connections_are_cut_off(self):
        with mock.patch.object(account_server, "REQUEST_DEADLINE", 1):
            slow = socket.create_connection(("127.0.0.1", self.server.server_port))
            slow.sendall(b"GET / HTTP/1.0\r\nX-Slow: ")
            time.sleep(2.5)
            slow.settimeout(5)
            try:
                self.assertEqual(slow.recv(1), b"")
            except ConnectionResetError:
                pass
            slow.close()

        idle = [socket.create_connection(("127.0.0.1", self.server.server_port)) for _ in range(account_server.MAX_CONNECTIONS_PER_IP)]
        try:
            time.sleep(0.5)
            extra = socket.create_connection(("127.0.0.1", self.server.server_port))
            extra.settimeout(5)
            try:
                self.assertEqual(extra.recv(1), b"")
            except ConnectionResetError:
                pass
            extra.close()
        finally:
            for connection in idle:
                connection.close()
        time.sleep(0.5)
        self.assertEqual(self.browser.request("/")[0], 200)


@unittest.skipUnless(os.getenv("ZATHROTH_TEST_URL"), "set ZATHROTH_TEST_URL for the read-only live smoke")
class LiveAccountManagerTest(unittest.TestCase):
    def test_running_service(self):
        browser = Browser(os.environ["ZATHROTH_TEST_URL"].rstrip("/"))
        status, body = browser.request("/health")
        self.assertEqual(status, 200, body)
        self.assertTrue(json.loads(body)["ready"])
        self.assertEqual(browser.request("/")[0], 200)
        self.assertIn("Create an account", browser.form("signin", identifier="1", password="1")[1])
        self.assertEqual(browser.game("1", "1")[1]["playdata"]["characters"][0]["name"], MANAGER_NAME)
        self.assertIn("playersonline", browser.game_status("cacheinfo")[1])


if __name__ == "__main__":
    unittest.main()
