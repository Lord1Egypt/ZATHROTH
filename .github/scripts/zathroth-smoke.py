"""Exercise the running ZATHROTH Compose stack on the loopback interface."""

from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib


HOST = "127.0.0.1"
KEY = Path(__file__).resolve().parents[2] / "key.pem"
MANAGER = "Account Manager"
XTEA_DELTA = 0x9E3779B9
MASK = 0xFFFFFFFF


def http_login(email, password):
    payload = json.dumps({"type": "login", "email": email, "password": password}).encode()
    request = urllib.request.Request(f"http://{HOST}:8088/login", payload, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def pack_string(value):
    value = value.encode()
    return struct.pack("<H", len(value)) + value


class GameClient:
    """A minimal 15.25 game client: session login, chat, and server text messages."""

    # The server blocks an IP for 3 s after more than 5 connections within
    # 5 s when two arrive within 500 ms, so connect at a client-like pace.
    last_connect = 0.0

    def __init__(self, session, character):
        time.sleep(max(0.0, GameClient.last_connect + 0.6 - time.monotonic()))
        GameClient.last_connect = time.monotonic()
        self.sock = socket.create_connection((HOST, 7172), timeout=10)
        self.key = struct.unpack("<IIII", os.urandom(16))
        self.sequence = 0
        self.texts = []
        length, = struct.unpack("<H", self.receive(2))
        _, _, opcode, timestamp, challenge = struct.unpack_from("<IBBIB", self.receive(8 * length + 4))
        assert opcode == 0x1F, hex(opcode)
        secret = b"\0" + struct.pack("<IIII", *self.key) + b"\0" + pack_string(session) + pack_string(character)
        secret += struct.pack("<IBH", timestamp, challenge, 0)
        encrypted = subprocess.check_output(
            ["openssl", "pkeyutl", "-encrypt", "-inkey", str(KEY), "-pkeyopt", "rsa_padding_mode:none"],
            input=secret.ljust(128, b"\0"),
        )
        packet = b"\x00\x0a" + struct.pack("<HHI", 2, 1525, 1525) + pack_string("15.25") + pack_string("") + b"\0" + encrypted
        padding = -len(packet) % 8
        packet = bytes((padding,)) + packet[1:] + b"\0" * padding
        self.sock.sendall(struct.pack("<HI", len(packet) // 8, zlib.adler32(packet)) + packet)

    def receive(self, count):
        data = bytearray()
        while len(data) < count:
            part = self.sock.recv(count - len(data))
            if not part:
                raise ConnectionError("The game server closed the connection.")
            data.extend(part)
        return bytes(data)

    def xtea(self, data, encrypt):
        output = bytearray()
        for x, y in struct.iter_unpack("<II", data):
            if encrypt:
                total = 0
                for _ in range(32):
                    x = (x + ((((y << 4) ^ (y >> 5)) + y) ^ (total + self.key[total & 3]))) & MASK
                    total = (total + XTEA_DELTA) & MASK
                    y = (y + ((((x << 4) ^ (x >> 5)) + x) ^ (total + self.key[(total >> 11) & 3]))) & MASK
            else:
                total = XTEA_DELTA * 32 & MASK
                for _ in range(32):
                    y = (y - ((((x << 4) ^ (x >> 5)) + x) ^ (total + self.key[(total >> 11) & 3]))) & MASK
                    total = (total - XTEA_DELTA) & MASK
                    x = (x - ((((y << 4) ^ (y >> 5)) + y) ^ (total + self.key[total & 3]))) & MASK
            output += struct.pack("<II", x, y)
        return bytes(output)

    def read_frame(self):
        size, = struct.unpack("<H", self.receive(2))
        frame = self.receive(size * 8 + 4)
        sequence, = struct.unpack_from("<I", frame)
        clear = self.xtea(frame[4:], encrypt=False)
        payload = clear[1:len(clear) - clear[0]]
        if sequence & (1 << 31):
            payload = zlib.decompressobj(-15).decompress(payload)
        if payload and payload[0] in (0x14, 0x16):
            length, = struct.unpack_from("<H", payload, 1)
            raise RuntimeError(f"Game refused login: {payload[3:3 + length].decode()}")
        marker = f"{MANAGER}: ".encode()
        start = payload.find(marker)
        while start >= 2:
            length, = struct.unpack_from("<H", payload, start - 2)
            self.texts.append(payload[start:start + length].decode())
            start = payload.find(marker, start + length)
        return payload

    def wait_for(self, expected, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(expected in text for text in self.texts):
                self.texts.clear()
                return
            self.read_frame()
        raise AssertionError(f"No Account Manager reply containing {expected!r}; last replies: {self.texts}")

    def send(self, payload):
        body = bytearray(b"\0" + payload)
        padding = -len(body) % 8
        body[0] = padding
        body += b"\0" * padding
        self.sequence += 1
        self.sock.sendall(struct.pack("<HI", len(body) // 8, self.sequence) + self.xtea(bytes(body), encrypt=True))

    def say(self, text, expected):
        self.send(b"\x96\x01" + pack_string(text))
        self.wait_for(expected)

    def close(self):
        self.send(b"\x14")
        self.sock.close()


def test_game_status():
    with socket.create_connection(("127.0.0.1", 7171), timeout=3) as conn:
        conn.sendall(bytes([6, 0, 255, 255]) + b"info")
        with conn.makefile("rb") as reply:
            status = ET.parse(reply).getroot()

    details = status.find("serverinfo")
    assert details.get("servername") == "ZATHROTH"
    assert details.get("client") == "15.25"
    assert details.get("ip") == "127.0.0.1"


def test_accounts():
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    base = "http://127.0.0.1:8088"

    def request(path, data=None, headers=None):
        req = urllib.request.Request(base + path, data, headers or {})
        with client.open(req, timeout=10) as response:
            return response.read().decode()

    def form(page, action, **fields):
        csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', page)
        assert csrf, "Account Manager form has no CSRF token"
        body = urllib.parse.urlencode({"action": action, "csrf": csrf[1], **fields})
        return request("/manage", body.encode())

    assert json.loads(request("/health"))["ready"]
    page = request("/")
    assert "ZATHROTH Account Manager" in page
    page = form(page, "signin", identifier="1", password="1")
    assert "Create an account" in page

    email = "compose-smoke@example.test"
    password = secrets.token_urlsafe(20)
    page = form(page, "register", name="composesmoke", email=email, password=password, confirm=password)
    assert "Account created." in page
    page = form(page, "character", name="Compose Scout", sex="1", vocation="1")
    assert "Character created." in page

    payload = json.dumps({"type": "login", "email": email, "password": password}).encode()
    login = json.loads(request("/login", payload, {"Content-Type": "application/json"}))
    assert login["session"]["sessionkey"]
    world, = login["playdata"]["worlds"]
    character, manager = login["playdata"]["characters"]
    assert world["externaladdressunprotected"] == "127.0.0.1"
    assert world["externalportunprotected"] == 7172
    assert (character["name"], manager["name"]) == ("Compose Scout", MANAGER)

    ident = character["characterid"]
    page = form(page, "delete", character=ident)
    assert "Character scheduled for deletion." in page
    page = form(page, "restore", character=ident)
    assert "Character restored." in page


def test_in_game_account_manager():
    login = http_login("1", "1")
    assert [c["name"] for c in login["playdata"]["characters"]] == [MANAGER]
    password = secrets.token_urlsafe(16)
    client = GameClient(login["session"]["sessionkey"], MANAGER)
    client.wait_for("Say 'account'")
    client.say("account", "password to be")
    client.say(password, "same password again")
    client.say(password, "account name to be")
    client.say("ingamesmoke", "are you sure")
    client.say("yes", "has been created")
    client.say("character", "character's name")
    client.say("Ingame Scout", "are you sure")
    client.say("yes", "'male' or 'female'")
    client.say("male", "'knight'")
    client.say("knight", "Are you sure")
    client.say("yes", "'Ingame Scout' has been created")
    client.close()

    login = http_login("ingamesmoke", password)
    names = [c["name"] for c in login["playdata"]["characters"]]
    assert names == ["Ingame Scout", MANAGER], names
    session = login["session"]["sessionkey"]
    client = GameClient(session, MANAGER)
    client.wait_for("'password' to change your password")
    client.close()

    # The character made in game loads and enters the world like any other.
    client = GameClient(session, "Ingame Scout")
    client.read_frame()
    client.close()


def test_account_manager_privacy():
    password = secrets.token_urlsafe(16)
    client = GameClient(http_login("1", "1")["session"]["sessionkey"], MANAGER)
    client.wait_for("Say 'account'")
    for line, reply in (("account", "password to be"), (password, "same password again"), (password, "account name"),
                        ("privacysmoke", "are you sure"), ("yes", "has been created"), ("character", "character's name"),
                        ("Privacy Watcher", "are you sure"), ("yes", "'male'"), ("female", "'druid'"), ("druid", "Are you sure"),
                        ("yes", "has been created")):
        client.say(line, reply)
    client.close()

    session = http_login("privacysmoke", password)["session"]["sessionkey"]
    watcher = GameClient(session, "Privacy Watcher")
    watcher.read_frame()
    # Two Account Managers online at once, standing where the watcher stands.
    first = GameClient(session, MANAGER)
    first.wait_for("'password' to change")
    second = GameClient(http_login("1", "1")["session"]["sessionkey"], MANAGER)
    second.wait_for("Say 'account'")
    secret = "Hidden" + secrets.token_hex(8)
    first.say("password", "new password to be")
    first.say(secret, "same password again")
    second.say(secret, "Say 'account'")
    watcher.sock.settimeout(1)
    seen = b""
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        try:
            seen += watcher.read_frame()
        except socket.timeout:
            pass
    assert secret.encode() not in seen, "A nearby player received text typed to the Account Manager"
    for client in (first, second, watcher):
        client.sock.settimeout(10)
        client.close()


if __name__ == "__main__":
    test_game_status()
    test_accounts()
    test_in_game_account_manager()
    test_account_manager_privacy()
    print("ZATHROTH status, browser and in-game account management, and game login passed.")
