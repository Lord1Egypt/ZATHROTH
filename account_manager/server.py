"""ZATHROTH's LAN account manager and modern game login endpoint."""

from datetime import datetime
import hashlib
import hmac
from html import escape
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
from threading import BoundedSemaphore, Lock
import time
from urllib.parse import parse_qs

from storage import AccountError, Accounts, START_VOCATIONS


ROOT = Path(__file__).resolve().parents[1]
STYLES = (Path(__file__).with_name("style.css")).read_bytes()
COOKIE = "zathroth_account"
WEB_SESSION_LIFETIME = 3600
MAX_BODY_BYTES = 16384


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
    def __init__(self, address, accounts, game_host, game_port, public_port):
        super().__init__(address, AccountHandler)
        self.accounts = accounts
        self.world = {
            "id": 0, "name": "ZATHROTH", "location": "LAN",
            "externaladdressprotected": game_host, "externaladdressunprotected": game_host,
            "externalportprotected": game_port, "externalportunprotected": game_port,
            "anticheatprotection": False, "previewstate": 0,
            "pvptype": 3,  # Retro Open PvP, matching config.lua.dist.
        }
        host = f"[{game_host}]" if ":" in game_host else game_host
        self.account_url = f"http://{host}:{public_port}/"
        self.secret = secrets.token_bytes(32)
        self.connections = BoundedSemaphore(12)
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

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        request.settimeout(10)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()


class AccountHandler(BaseHTTPRequestHandler):
    server_version = "ZATHROTH"
    sys_version = ""

    @property
    def accounts(self):
        return self.server.accounts

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

    def send_page(self, body, *, message="", status=HTTPStatus.OK, cookie=None):
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
        cookie = f"{COOKIE}={value}; Path=/; Max-Age={WEB_SESSION_LIFETIME}; HttpOnly; SameSite=Strict"
        return nonce, cookie

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
""", "Create account") + self.form("logout", nonce, "", "Back to sign in", "secondary")
        else:
            content = self.form("signin", nonce, """
<h2>Sign in</h2>
<p>To create your first account, enter <strong>1</strong> in both fields.</p>
<label>Account name or email <input name="identifier" autocomplete="username" maxlength="255" required></label>
<label>Password <input name="password" type="password" autocomplete="current-password" maxlength="128" required></label>
""", "Sign in")
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
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except sqlite3.Error:
            if self.path == "/health":
                self.json_response({"ready": False}, HTTPStatus.SERVICE_UNAVAILABLE)
            else:
                self.send_page("", message="The game database is starting. Try again shortly.", status=HTTPStatus.SERVICE_UNAVAILABLE)

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
            if not self.server.allow_auth(self.client_address[0]):
                self.json_response({"errorCode": 2, "errorMessage": "Too many attempts. Try again shortly."})
                return
            if identifier == "1" and password == "1":
                self.json_response({"errorCode": 2, "errorMessage": f"Open {self.server.account_url} in your browser and sign in with 1 / 1 to create an account."})
                return
            with self.server.hashers:
                account = self.accounts.authenticate(identifier.strip(), password)
            key, rows = self.accounts.start_game_session(account)
            if key is None:
                self.json_response({"errorCode": 2, "errorMessage": f"Create a character at {self.server.account_url} and try again."})
                return
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
                "playdata": {"worlds": [self.server.world], "characters": [self.game_character(row) for row in rows]},
            })
        except AccountError as error:
            self.json_response({"errorCode": 3, "errorMessage": str(error)})
        except (ValueError, RecursionError):
            self.json_response({"errorCode": 2, "errorMessage": "Invalid login request."}, HTTPStatus.BAD_REQUEST)
        except (sqlite3.Error, OSError):
            self.json_response({"errorCode": 2, "errorMessage": "The game database is starting. Try again shortly."}, HTTPStatus.SERVICE_UNAVAILABLE)

    def game_status(self, action):
        if action == "cacheinfo":
            return {
                "playersonline": self.accounts.online_count(), "discord_online": "0",
                "gamingyoutubestreams": "0", "gamingyoutubeviewer": "0",
            }
        if action == "eventschedule":
            return client_events()
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
            if action in ("signin", "register", "password") and not self.server.allow_auth(self.client_address[0]):
                raise AccountError("Too many attempts. Try again shortly.")
            if action == "signin" and subject == "anonymous":
                identifier = fields.get("identifier", "").strip()
                password = fields.get("password", "")
                if identifier == "1" and password == "1":
                    self.browser_page(("guest", None, ""))
                else:
                    with self.server.hashers:
                        account = self.accounts.authenticate(identifier, password)
                    self.browser_page(("account", account, ""))
            elif action == "register" and subject == "guest":
                self.check_confirmation(fields)
                with self.server.hashers:
                    account = self.accounts.register(fields.get("name", "").strip(), fields.get("email", "").strip(), fields["password"])
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
            with self.server.hashers:
                account = self.accounts.change_password(account, fields.get("current", ""), fields["password"])
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
        int(os.environ.get("ZATHROTH_ACCOUNT_PUBLIC_PORT", str(port))),
    )
    with server:
        print(f"ZATHROTH Account Manager and game login listening on port {port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
