"""Exercise the running ZATHROTH Compose stack on the loopback interface."""

from http.cookiejar import CookieJar
import json
import re
import secrets
import socket
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


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
    character, = login["playdata"]["characters"]
    assert world["externaladdressunprotected"] == "127.0.0.1"
    assert world["externalportunprotected"] == 7172
    assert character["name"] == "Compose Scout"

    ident = character["characterid"]
    page = form(page, "delete", character=ident)
    assert "Character scheduled for deletion." in page
    page = form(page, "restore", character=ident)
    assert "Character restored." in page


if __name__ == "__main__":
    test_game_status()
    test_accounts()
    print("ZATHROTH status, browser account management, and HTTP game login passed.")
