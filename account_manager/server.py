"""ZATHROTH's account manager and modern game login endpoint."""

from datetime import datetime
import hashlib
import hmac
from html import escape
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
from threading import BoundedSemaphore, Lock, Thread, Timer
import time
from urllib.parse import parse_qs, quote, unquote

from guard import AuthGuard, Captchas
from storage import AccountError, Accounts, START_VOCATIONS, WrongPassword


ROOT = Path(__file__).resolve().parents[1]
STYLES = (Path(__file__).with_name("style.css")).read_bytes()
COOKIE = "zathroth_account"
WEB_SESSION_LIFETIME = 3600
MAX_BODY_BYTES = 16384
MAX_CONNECTIONS = 64
MAX_CONNECTIONS_PER_IP = 8
# One request per connection (HTTP/1.0). The socket timeout only limits the
# wait for each read, so a client sending a byte every few seconds would hold
# a slot forever; this caps the whole connection.
REQUEST_DEADLINE = 30
BLOCKED_MESSAGE = "Too many failed attempts. Try again in a few minutes."
# Game client packages offered for download: the files in <repository>/downloads.
DOWNLOAD_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,100}\.(?:zip|7z|rar|exe|msi)")
MAX_DOWNLOADS = 4
MAX_DOWNLOADS_PER_ADDRESS = 2
# A download may take as long as the visitor needs, but a visitor that stops
# reading for this long is dropped.
DOWNLOAD_STALL_SECONDS = 60


class RequestError(ValueError):
    """An invalid HTTP request."""


def event_date(date, hour):
    if hour.count(":") == 1:
        hour += ":00"
    return int(datetime.strptime(f"{date} {hour}", "%m/%d/%Y %H:%M:%S").timestamp())


def client_events():
    schedule = ROOT / "data/json/eventscheduler/events.json"
    events = []
    for event in json.loads(schedule.read_text(encoding="utf-8"))["events"]:
        hour = event.get("hour") or ""
        try:
            start = event_date(event["startdate"], event.get("starthour") or hour or "00:00")
            end = event_date(event["enddate"], event.get("endhour") or hour or "23:59:59")
        except (KeyError, ValueError):
            continue
        if start > end:
            continue
        colors = event.get("colors") or {}
        details = event.get("details") or {}
        events.append({
            "name": event.get("name", ""), "description": event.get("description", ""),
            "startdate": start, "enddate": end,
            "colorlight": colors.get("colorlight", "#514331"),
            "colordark": colors.get("colordark", "#231f1a"),
            "displaypriority": int(details.get("displaypriority", 0)),
            "isseasonal": str(details.get("isseasonal", "")).lower() in ("1", "true"),
            "specialevent": str(details.get("specialevent", "")).lower() in ("1", "true"),
        })
    return {"eventlist": events, "lastupdatetimestamp": int(schedule.stat().st_mtime)}


class AccountServer(ThreadingHTTPServer):
    def __init__(self, address, accounts, game_host, game_port, captcha=True, trusted_proxy="", lan_host="", downloads=None):
        super().__init__(address, AccountHandler)
        self.accounts = accounts
        self.captcha_enabled = captcha
        # Host name or address of the HTTPS reverse proxy in front of this
        # service. Only it may say, through X-Forwarded-For and -Proto, who the
        # real visitor is and whether they used HTTPS.
        self.trusted_proxy = trusted_proxy
        # Clients on the home network get this game address instead of
        # game_host: a router often cannot loop back to its own public address.
        self.lan_host = lan_host
        self.proxy_addresses = frozenset()
        if trusted_proxy:
            try:
                self.proxy_addresses = frozenset([str(ipaddress.ip_address(trusted_proxy))])
            except ValueError:
                # A host name: the lookup of a name that does not exist can take
                # many seconds, so it never runs inside a request.
                Thread(target=self.watch_proxy, daemon=True).start()
        self.captchas = Captchas()
        self.guard = AuthGuard()
        self.active = {}
        self.world = {
            "id": 0, "name": "ZATHROTH", "location": "LAN",
            "externaladdressprotected": game_host, "externaladdressunprotected": game_host,
            "externalportprotected": game_port, "externalportunprotected": game_port,
            "anticheatprotection": False, "previewstate": 0,
            "pvptype": 3,  # Retro Open PvP, matching config.lua.dist.
        }
        self.secret = secrets.token_bytes(32)
        self.connections = BoundedSemaphore(MAX_CONNECTIONS)
        self.downloads_dir = Path(downloads) if downloads else ROOT / "downloads"
        self.downloading = BoundedSemaphore(MAX_DOWNLOADS)
        self.downloads_by_address = {}
        self.deadlines = {}
        self.hashers = BoundedSemaphore(2)
        self.rate_lock = Lock()
        self.rate_window = 0
        self.rate_counts = {}

    def signature(self, value):
        return hmac.new(self.secret, value.encode(), hashlib.sha256).hexdigest()

    def allow_auth(self, address):
        with self.rate_lock:
            window = int(time.monotonic()) // 60
            if window != self.rate_window:
                self.rate_window = window
                self.rate_counts.clear()
            if len(self.rate_counts) >= 4096 and address not in self.rate_counts:
                return False
            count = self.rate_counts.get(address, 0)
            if count >= 30:
                return False
            self.rate_counts[address] = count + 1
            return True

    def world_for(self, address):
        if self.lan_host:
            try:
                private = ipaddress.ip_address(address).is_private
            except ValueError:
                private = False
            if private:
                return {**self.world, "externaladdressprotected": self.lan_host, "externaladdressunprotected": self.lan_host}
        return self.world

    def watch_proxy(self):
        """Keeps the proxy's current addresses up to date; its container may start later or get a new address."""
        while True:
            try:
                self.proxy_addresses = frozenset(info[4][0] for info in socket.getaddrinfo(self.trusted_proxy, None, socket.AF_INET))
            except OSError:
                self.proxy_addresses = frozenset()
            time.sleep(30)

    def is_trusted_proxy(self, address):
        return address in self.proxy_addresses

    def take_slot(self, address):
        if not self.connections.acquire(blocking=False):
            return False
        with self.rate_lock:
            # The proxy carries many visitors over a few connections.
            if self.active.get(address, 0) >= MAX_CONNECTIONS_PER_IP and not self.is_trusted_proxy(address):
                self.connections.release()
                return False
            self.active[address] = self.active.get(address, 0) + 1
        return True

    def release_slot(self, address):
        with self.rate_lock:
            if self.active[address] <= 1:
                del self.active[address]
            else:
                self.active[address] -= 1
        self.connections.release()

    def process_request(self, request, client_address):
        if not self.take_slot(client_address[0]):
            self.shutdown_request(request)
            return
        request.settimeout(10)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.release_slot(client_address[0])
            raise

    def process_request_thread(self, request, client_address):
        deadline = Timer(REQUEST_DEADLINE, self.abandon, (request,))
        deadline.daemon = True
        self.deadlines[request] = deadline
        deadline.start()
        try:
            super().process_request_thread(request, client_address)
        finally:
            deadline.cancel()
            self.deadlines.pop(request, None)
            self.release_slot(client_address[0])

    def stop_deadline(self, request):
        """Downloads outlast the request deadline; they have their own stall timeout."""
        deadline = self.deadlines.get(request)
        if deadline:
            deadline.cancel()

    def available_downloads(self):
        try:
            paths = sorted(self.downloads_dir.iterdir())
        except OSError:
            return []
        return [(path.name, path.stat().st_size) for path in paths if DOWNLOAD_NAME.fullmatch(path.name) and path.is_file() and not path.is_symlink()]

    @staticmethod
    def abandon(request):
        try:
            request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class AccountHandler(BaseHTTPRequestHandler):
    server_version = "ZATHROTH"
    sys_version = ""

    @property
    def accounts(self):
        return self.server.accounts

    @property
    def behind_proxy(self):
        return self.server.is_trusted_proxy(self.client_address[0])

    @property
    def address(self):
        """The visitor's address: the one the trusted proxy saw, otherwise the connection's."""
        peer = self.client_address[0]
        if self.behind_proxy:
            try:
                return str(ipaddress.ip_address(self.headers.get("X-Forwarded-For", "").split(",")[-1].strip()))
            except ValueError:
                pass
        return peer

    @property
    def secure(self):
        return self.behind_proxy and self.headers.get("X-Forwarded-Proto", "") == "https"

    def address_string(self):
        return self.address

    def respond(self, status, mime, body, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, payload, status=HTTPStatus.OK):
        self.respond(status, "application/json; charset=utf-8", json.dumps(payload).encode())

    def read_body(self):
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
            raise RequestError("A content length is required.")
        try:
            length = int(lengths[0])
        except ValueError as error:
            raise RequestError("Invalid content length.") from error
        if not 0 < length <= MAX_BODY_BYTES:
            raise RequestError("Invalid request size.")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise RequestError("Incomplete request.")
        return raw.decode("utf-8")

    def downloads_section(self):
        files = self.server.available_downloads()
        if not files:
            return ""
        items = "".join(
            f'<li><div><a href="/downloads/{quote(name)}">{escape(name)}</a><br>{size / 1048576:,.0f} MB</div></li>'
            for name, size in files
        )
        return f"<section><h2>Download the game client</h2><ul>{items}</ul></section>"

    def send_page(self, body, *, message="", status=HTTPStatus.OK, cookie=None):
        body += self.downloads_section()
        notice = f'<p class="notice" role="status">{escape(message)}</p>' if message else ""
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZATHROTH Account Manager</title>
<link rel="stylesheet" href="/style.css">
</head>
<body><main><header><h1>ZATHROTH</h1><p>Account Manager</p></header>
{notice}{body}
</main></body></html>"""
        self.respond(status, "text/html; charset=utf-8", page.encode(), cookie)

    def session(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            return "anonymous", None, ""
        if COOKIE not in cookies:
            return "anonymous", None, ""
        try:
            subject, expires, nonce, tag, signature = cookies[COOKIE].value.split(".")
            unsigned = ".".join((subject, expires, nonce, tag))
            if not hmac.compare_digest(self.server.signature(unsigned), signature) or int(expires) <= time.time():
                return "anonymous", None, ""
        except (ValueError, TypeError):
            return "anonymous", None, ""
        if subject in ("anonymous", "guest"):
            return subject, None, nonce
        account = self.accounts.get(int(subject))
        if account and hmac.compare_digest(self.server.signature(account["password"]), tag):
            return "account", account, nonce
        return "anonymous", None, ""

    def new_session(self, subject, account):
        nonce = secrets.token_hex(32)
        expires = int(time.time()) + WEB_SESSION_LIFETIME
        if account:
            subject = str(account["id"])
            tag = self.server.signature(account["password"])
        else:
            tag = "-"
        unsigned = f"{subject}.{expires}.{nonce}.{tag}"
        value = f"{unsigned}.{self.server.signature(unsigned)}"
        cookie = f"{COOKIE}={value}; Path=/; Max-Age={WEB_SESSION_LIFETIME}; HttpOnly; SameSite=Strict" + ("; Secure" if self.secure else "")
        return nonce, cookie

    def captcha_block(self):
        token, picture = self.server.captchas.issue()
        return f"""<div class="captcha-box">{picture}</div>
<input type="hidden" name="captcha_id" value="{token}">
<label>Type the characters from the picture <input name="captcha" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="12" required></label>
"""

    def check_captcha(self, fields):
        if self.server.captcha_enabled and not self.server.captchas.verify(fields.get("captcha_id", ""), fields.get("captcha", "")):
            raise AccountError("The characters did not match. Try the new picture.")

    def form(self, action, nonce, fields, label, button_class=""):
        return f"""<form action="/manage" method="post">
<input type="hidden" name="action" value="{action}">
<input type="hidden" name="csrf" value="{nonce}">
{fields}<button class="{button_class}">{label}</button></form>"""

    def browser_page(self, session, *, message="", status=HTTPStatus.OK):
        subject, account, nonce = session
        cookie = None
        if not nonce:
            nonce, cookie = self.new_session(subject, account)
        if account:
            content = self.character_page(account, nonce)
        elif subject == "guest":
            content = self.form("register", nonce, """
<h2>Create an account</h2>
<label>Account name <input name="name" autocomplete="username" minlength="3" maxlength="32" required></label>
<label>Email <input name="email" type="email" autocomplete="email" maxlength="255" required></label>
<label>Password <input name="password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
<label>Confirm password <input name="confirm" type="password" autocomplete="new-password" maxlength="128" required></label>
""" + (self.captcha_block() if self.server.captcha_enabled else ""), "Create account") + self.form("logout", nonce, "", "Back to sign in", "secondary")
        else:
            challenge = self.captcha_block() if self.server.captcha_enabled and self.server.guard.needs_captcha(self.address) else ""
            content = self.form("signin", nonce, """
<h2>Sign in</h2>
<p>To create your first account, enter <strong>1</strong> in both fields.</p>
<label>Account name or email <input name="identifier" autocomplete="username" maxlength="255" required></label>
<label>Password <input name="password" type="password" autocomplete="current-password" maxlength="128" required></label>
""" + challenge, "Sign in")
        self.send_page(content, message=message, status=status, cookie=cookie)

    def character_page(self, account, nonce):
        options = "".join(
            f'<option value="{vocation}">{escape(self.accounts.vocations[vocation])}</option>'
            for vocation in START_VOCATIONS if vocation in self.accounts.vocations
        )
        rows = []
        for character in self.accounts.characters(account["id"]):
            action = ""
            field = f'<input type="hidden" name="character" value="{character["id"]}">'
            if character["deletion"]:
                date = time.strftime("%Y-%m-%d", time.gmtime(character["deletion"]))
                state = f"Deletion scheduled for {date} UTC"
                if character["deletion"] > time.time():
                    action = self.form("restore", nonce, field, "Restore", "secondary")
            elif character["online"]:
                state = "Online"
            else:
                state = "Offline"
                action = self.form("delete", nonce, field, "Schedule deletion", "secondary")
            rows.append(f"<li><div><strong>{escape(character['name'])}</strong><br>{state}</div>{action}</li>")
        characters = "<ul>" + "".join(rows) + "</ul>" if rows else "<p>You don’t have any characters yet.</p>"
        create = self.form("character", nonce, f"""
<h2>Create a character</h2>
<label>Name <input name="name" minlength="4" maxlength="29" required></label>
<label>Vocation <select name="vocation">{options}</select></label>
<label>Outfit <select name="sex"><option value="0">Female</option><option value="1">Male</option></select></label>
""", "Create character")
        password = self.form("password", nonce, """
<h2>Change password</h2>
<label>Current password <input name="current" type="password" autocomplete="current-password" maxlength="128" required></label>
<label>New password <input name="password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
<label>Confirm new password <input name="confirm" type="password" autocomplete="new-password" maxlength="128" required></label>
""", "Change password")
        logout = self.form("logout", nonce, "", "Sign out", "secondary")
        return f"<section><h2>{escape(account['name'])}’s characters</h2>{characters}</section>{create}{password}{logout}"

    def do_GET(self):
        if self.path == "/style.css":
            self.respond(HTTPStatus.OK, "text/css; charset=utf-8", STYLES)
            return
        try:
            if self.path == "/health":
                ready = self.accounts.ready()
                self.json_response({"ready": ready}, HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE)
            elif self.path == "/":
                self.browser_page(self.session())
            elif self.path.startswith("/downloads/"):
                self.send_download()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except sqlite3.Error:
            if self.path == "/health":
                self.json_response({"ready": False}, HTTPStatus.SERVICE_UNAVAILABLE)
            else:
                self.send_page("", message="The game database is starting. Try again shortly.", status=HTTPStatus.SERVICE_UNAVAILABLE)

    def send_download(self):
        name = unquote(self.path[len("/downloads/"):].split("?", 1)[0])
        path = self.server.downloads_dir / name
        if not DOWNLOAD_NAME.fullmatch(name) or path.is_symlink() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        start, end, status = 0, size - 1, HTTPStatus.OK
        requested = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
        if requested and (requested[1] or requested[2]):
            if requested[1]:
                start = int(requested[1])
                end = min(int(requested[2]), size - 1) if requested[2] else size - 1
            else:
                start = max(0, size - int(requested[2]))
            if start >= size or start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = HTTPStatus.PARTIAL_CONTENT
        address = self.address
        with self.server.rate_lock:
            allowed = self.server.downloads_by_address.get(address, 0) < MAX_DOWNLOADS_PER_ADDRESS and self.server.downloading.acquire(blocking=False)
            if allowed:
                self.server.downloads_by_address[address] = self.server.downloads_by_address.get(address, 0) + 1
        if not allowed:
            self.respond(HTTPStatus.SERVICE_UNAVAILABLE, "text/plain; charset=utf-8", b"Too many downloads are running. Try again in a few minutes.\n")
            return
        try:
            self.server.stop_deadline(self.request)
            self.connection.settimeout(DOWNLOAD_STALL_SECONDS)
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Accept-Ranges", "bytes")
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with path.open("rb") as handle:
                self.connection.sendfile(handle, start, end - start + 1)
        except OSError:
            pass  # the visitor went away or stopped reading
        finally:
            with self.server.rate_lock:
                remaining = self.server.downloads_by_address[address] - 1
                if remaining:
                    self.server.downloads_by_address[address] = remaining
                else:
                    del self.server.downloads_by_address[address]
            self.server.downloading.release()

    def do_POST(self):
        if self.path in ("/login", "/login.php", "/"):
            self.handle_game_login()
        elif self.path == "/manage":
            self.handle_browser_post()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def handle_game_login(self):
        try:
            payload = json.loads(self.read_body())
            if not isinstance(payload, dict):
                raise RequestError("Use a JSON object.")
            action = payload.get("type")
            if action != "login":
                self.json_response(self.game_status(action))
                return
            identifier = payload.get("email", payload.get("accountname", ""))
            password = payload.get("password", "")
            if not isinstance(identifier, str) or not isinstance(password, str) or len(identifier) > 255:
                raise RequestError("Use a valid account name and password.")
            address = self.address
            if not self.server.allow_auth(address):
                self.json_response({"errorCode": 2, "errorMessage": "Too many attempts. Try again shortly."})
                return
            if identifier.strip() == "1" and password == "1":
                key, account, rows = self.accounts.start_game_session()
            else:
                if self.server.guard.blocked(address, identifier):
                    self.log_message("%s", "game login blocked: too many failures")
                    self.json_response({"errorCode": 2, "errorMessage": BLOCKED_MESSAGE})
                    return
                try:
                    with self.server.hashers:
                        account = self.accounts.authenticate(identifier.strip(), password)
                except WrongPassword:
                    self.server.guard.failed(address, identifier)
                    raise
                key, account, rows = self.accounts.start_game_session(account)
            device_cookie = payload.get("devicecookie", "")
            lastday = max(0, account["lastday"])
            self.json_response({
                "devicecookie": device_cookie if isinstance(device_cookie, str) else "",
                "loginemail": account["email"],
                "session": {
                    "sessionkey": key, "status": "active", "ispremium": lastday > time.time(),
                    "premiumuntil": lastday, "lastlogintime": max(row["lastlogin"] for row in rows),
                    "isreturner": False, "showrewardnews": False, "recoverysetupcomplete": False,
                    "returnernotification": False, "optiontracking": False, "fpstracking": False,
                },
                "playdata": {"worlds": [self.server.world_for(address)], "characters": [self.game_character(row) for row in rows]},
            })
        except AccountError as error:
            self.json_response({"errorCode": 3, "errorMessage": str(error)})
        except (ValueError, RecursionError):
            self.json_response({"errorCode": 2, "errorMessage": "Invalid login request."}, HTTPStatus.BAD_REQUEST)
        except sqlite3.Error:
            self.json_response({"errorCode": 2, "errorMessage": "The game database is starting. Try again shortly."}, HTTPStatus.SERVICE_UNAVAILABLE)

    def game_status(self, action):
        if action == "cacheinfo":
            return {
                "playersonline": self.accounts.online_count(), "discord_online": "0",
                "gamingyoutubestreams": "0", "gamingyoutubeviewer": "0",
            }
        if action == "eventschedule":
            try:
                return client_events()
            except (OSError, ValueError):
                return {"errorCode": 2, "errorMessage": "The event calendar is unavailable."}
        if action == "boostedcreature":
            creature, boss = self.accounts.boosted_races()
            return {"boostedcreature": bool(creature), "creatureraceid": creature, "bossraceid": boss}
        return {"errorCode": 2, "errorMessage": "This request is unavailable."}

    def game_character(self, row):
        return {
            "worldid": 0, "characterid": row["id"], "name": row["name"], "level": row["level"],
            "vocation": self.accounts.vocations.get(row["vocation"], "None"), "ismale": row["sex"] == 1,
            "outfitid": row["looktype"], "headcolor": row["lookhead"], "torsocolor": row["lookbody"],
            "legscolor": row["looklegs"], "detailcolor": row["lookfeet"], "addonsflags": row["lookaddons"],
            "dailyrewardstate": 0, "ismaincharacter": False, "ishidden": False, "tutorial": False,
        }

    def handle_browser_post(self):
        session = ("anonymous", None, "")
        try:
            if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                raise RequestError("Submit the form from the Account Manager page.")
            if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
                raise RequestError("Submit the form from the Account Manager page.")
            fields = parse_qs(self.read_body(), keep_blank_values=True, max_num_fields=12, errors="strict")
            if any(len(values) != 1 for values in fields.values()):
                raise RequestError("Repeated form field.")
            fields = {name: values[0] for name, values in fields.items()}
            session = self.session()
            subject, account, nonce = session
            if not nonce or not hmac.compare_digest(nonce.encode(), fields.get("csrf", "").encode()):
                raise RequestError("This form expired. Please try again.")
            action = fields.get("action")
            if action == "logout":
                self.browser_page(("anonymous", None, ""))
                return
            address = self.address
            guard = self.server.guard
            if action in ("signin", "register", "password") and not self.server.allow_auth(address):
                raise AccountError("Too many attempts. Try again shortly.")
            if action == "signin" and subject == "anonymous":
                identifier = fields.get("identifier", "").strip()
                password = fields.get("password", "")
                if identifier == "1" and password == "1":
                    self.browser_page(("guest", None, ""))
                else:
                    if guard.blocked(address, identifier):
                        self.log_message("%s", "sign-in blocked: too many failures")
                        raise AccountError(BLOCKED_MESSAGE)
                    if guard.needs_captcha(address):
                        self.check_captcha(fields)
                    try:
                        with self.server.hashers:
                            account = self.accounts.authenticate(identifier, password)
                    except WrongPassword:
                        guard.failed(address, identifier)
                        raise
                    self.browser_page(("account", account, ""))
            elif action == "register" and subject == "guest":
                self.check_confirmation(fields)
                self.check_captcha(fields)
                if not guard.may_register(address):
                    self.log_message("%s", "registration refused: too many new accounts")
                    raise AccountError("Too many accounts were created from your address. Try again tomorrow.")
                with self.server.hashers:
                    account = self.accounts.register(fields.get("name", "").strip(), fields.get("email", "").strip(), fields["password"])
                guard.registered(address)
                self.browser_page(("account", account, ""), message="Account created. Create your first character below.")
            elif account:
                self.update_account(session, action, fields)
            else:
                raise RequestError("Sign in to use this action.")
        except AccountError as error:
            self.browser_page(session, message=str(error), status=HTTPStatus.BAD_REQUEST)
        except ValueError as error:
            message = str(error) if isinstance(error, RequestError) else "Invalid form values. Please try again."
            self.browser_page(session, message=message, status=HTTPStatus.BAD_REQUEST)
        except sqlite3.Error:
            self.send_page("", message="The game database is busy or starting. Try again shortly.", status=HTTPStatus.SERVICE_UNAVAILABLE)

    def check_confirmation(self, fields):
        if "password" not in fields or fields["password"] != fields.get("confirm"):
            raise AccountError("The two passwords do not match.")

    def update_account(self, session, action, fields):
        _, account, _ = session
        if action == "character":
            self.accounts.create_character(account, fields.get("name", "").strip(), int(fields.get("sex", "")), int(fields.get("vocation", "")))
            self.browser_page(session, message="Character created. You can now select it in the game client.")
        elif action in ("delete", "restore"):
            character_id = int(fields.get("character", ""))
            if not 0 < character_id <= 0xffffffff:
                raise RequestError("Invalid character ID.")
            self.accounts.set_character_deletion(account, character_id, delete=(action == "delete"))
            message = "Character restored." if action == "restore" else "Character scheduled for deletion. You can restore it within seven days."
            self.browser_page(session, message=message)
        elif action == "password":
            self.check_confirmation(fields)
            address, guard = self.address, self.server.guard
            if guard.blocked(address, account["name"]):
                self.log_message("%s", "password change blocked: too many failures")
                raise AccountError(BLOCKED_MESSAGE)
            try:
                with self.server.hashers:
                    account = self.accounts.change_password(account, fields.get("current", ""), fields["password"])
            except WrongPassword:
                guard.failed(address, account["name"])
                raise
            self.browser_page(("account", account, ""), message="Password changed.")
        else:
            raise RequestError("Unknown account action.")

    def log_request(self, code="-", size="-"):
        # Request targets and bodies can contain credentials. Log only method and status.
        if getattr(self, "path", "") not in ("/health", "/style.css"):
            self.log_message("%s %s", self.command, code)


def main():
    accounts = Accounts(
        os.environ.get("ZATHROTH_DB_PATH", str(ROOT / "zathroth.sqlite3")),
        int(os.environ.get("ZATHROTH_START_TOWN_ID", "0")),
        ROOT / "data/XML/vocations.xml",
    )
    port = int(os.environ.get("ZATHROTH_ACCOUNT_PORT", "8088"))
    server = AccountServer(
        ("0.0.0.0", port), accounts,
        os.environ.get("ZATHROTH_SERVER_IP", "192.168.1.104"),
        int(os.environ.get("ZATHROTH_GAME_PORT", "7172")),
        captcha=os.environ.get("ZATHROTH_CAPTCHA", "on").lower() != "off",
        trusted_proxy=os.environ.get("ZATHROTH_TRUSTED_PROXY", ""),
        lan_host=os.environ.get("ZATHROTH_LAN_IP", ""),
    )
    with server:
        print(f"ZATHROTH Account Manager and game login listening on port {port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
