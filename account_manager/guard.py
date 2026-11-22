"""Abuse limits for the internet-facing account service.

Failed-login throttling for the browser and game logins, a cap on new accounts
per address, and a self-hosted CAPTCHA. Everything lives in memory: restarting
the service clears it, which is fine for windows of minutes to a day.
"""

from collections import OrderedDict, deque
import hmac
import math
import secrets
from threading import Lock
import time

IP_WINDOW = 15 * 60
IP_CAPTCHA_AFTER = 3
IP_BLOCK_AFTER = 10
ACCOUNT_WINDOW = 60 * 60
ACCOUNT_BLOCK_AFTER = 40
REGISTRATIONS_PER_IP = 5
REGISTRATIONS_PER_HOUR = 60
MAX_TRACKED = 20000


class AuthGuard:
    """Counts failed sign-ins per address and per account, and new accounts per address."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = Lock()
        self.ip_failures = {}
        self.account_failures = {}
        self.registrations = {}
        self.recent_registrations = deque()

    @staticmethod
    def _count(table, key, window, now):
        events = table.get(key)
        if events is None:
            return 0
        while events and events[0] <= now - window:
            events.popleft()
        if not events:
            del table[key]
        return len(events)

    @staticmethod
    def _add(table, key, window, now):
        if key not in table and len(table) >= MAX_TRACKED:
            for old in [k for k, events in table.items() if not events or events[-1] <= now - window]:
                del table[old]
            if len(table) >= MAX_TRACKED:
                del table[next(iter(table))]
        table.setdefault(key, deque()).append(now)

    @staticmethod
    def _key(identifier):
        return identifier.strip().lower()[:255]

    def blocked(self, address, identifier=""):
        """True when this address, or the account it is trying, has failed too often."""
        now = self.clock()
        key = self._key(identifier)
        with self.lock:
            if self._count(self.ip_failures, address, IP_WINDOW, now) >= IP_BLOCK_AFTER:
                return True
            return bool(key) and self._count(self.account_failures, key, ACCOUNT_WINDOW, now) >= ACCOUNT_BLOCK_AFTER

    def needs_captcha(self, address):
        with self.lock:
            return self._count(self.ip_failures, address, IP_WINDOW, self.clock()) >= IP_CAPTCHA_AFTER

    def failed(self, address, identifier=""):
        now = self.clock()
        key = self._key(identifier)
        with self.lock:
            self._add(self.ip_failures, address, IP_WINDOW, now)
            if key:
                self._add(self.account_failures, key, ACCOUNT_WINDOW, now)

    def may_register(self, address):
        now = self.clock()
        with self.lock:
            while self.recent_registrations and self.recent_registrations[0] <= now - 3600:
                self.recent_registrations.popleft()
            return (
                len(self.recent_registrations) < REGISTRATIONS_PER_HOUR
                and self._count(self.registrations, address, 86400, now) < REGISTRATIONS_PER_IP
            )

    def registered(self, address):
        now = self.clock()
        with self.lock:
            self._add(self.registrations, address, 86400, now)
            self.recent_registrations.append(now)


ALPHABET = "ACEFHKLMNPTWX23456789"
LENGTH = 5
LIFETIME = 600
MAX_PENDING = 2048
WIDTH, HEIGHT = 216, 72

# Strokes on a 4 x 6 grid, y pointing down. Only characters that stay distinct
# after rotation and warping.
GLYPHS = {
    "A": [[(0, 6), (2, 0), (4, 6)], [(1, 4), (3, 4)]],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "F": [[(4, 0), (0, 0), (0, 6)], [(0, 3), (3, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "K": [[(0, 0), (0, 6)], [(4, 0), (0, 3), (4, 6)]],
    "L": [[(0, 0), (0, 6), (4, 6)]],
    "M": [[(0, 6), (0, 0), (2, 3), (4, 0), (4, 6)]],
    "N": [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    "P": [[(0, 6), (0, 0), (4, 0), (4, 3), (0, 3)]],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    "W": [[(0, 0), (1, 6), (2, 2), (3, 6), (4, 0)]],
    "X": [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    "2": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (0, 6), (4, 6)]],
    "3": [[(0, 0), (4, 0), (2, 2.5), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "4": [[(3, 6), (3, 0), (0, 4), (4, 4)]],
    "5": [[(4, 0), (0, 0), (0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6)]],
    "6": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]],
    "7": [[(0, 0), (4, 0), (1.5, 6)]],
    "8": [
        [(1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3), (0, 2), (0, 1), (1, 0)],
        [(1, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3)],
    ],
    "9": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (4, 3)]],
}
assert set(ALPHABET) == set(GLYPHS)


def draw(code, rng):
    """An inline SVG of `code` drawn as warped strokes, so no text holds the answer."""
    phase = rng.uniform(0, math.tau)
    frequency = rng.uniform(0.045, 0.07)
    amplitude = rng.uniform(2.5, 4)
    paths = []
    for index, char in enumerate(code):
        unit = rng.uniform(6.3, 7.4)
        angle = rng.uniform(-0.3, 0.3)
        cos, sin = math.cos(angle), math.sin(angle)
        left = 24 + index * 38 + rng.uniform(-3, 3)
        top = (HEIGHT - 6 * unit) / 2 + rng.uniform(-4, 4)
        for stroke in GLYPHS[char]:
            points = []
            for (x1, y1), (x2, y2) in zip(stroke, stroke[1:]):
                steps = max(1, math.ceil(math.hypot(x2 - x1, y2 - y1) / 0.7))
                points.extend((x1 + (x2 - x1) * s / steps, y1 + (y2 - y1) * s / steps) for s in range(steps))
            points.append(stroke[-1])
            out = []
            for x, y in points:
                x = (x - 2 + rng.uniform(-0.12, 0.12)) * unit
                y = (y - 3 + rng.uniform(-0.12, 0.12)) * unit
                x, y = x * cos - y * sin, x * sin + y * cos
                x += left + 2 * unit
                y += top + 3 * unit
                out.append(f"{x:.1f} {y + amplitude * math.sin(x * frequency + phase):.1f}")
            paths.append("M" + "L".join(out))
    noise = []
    for _ in range(5):
        ends = [(rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT)) for _ in range(3)]
        noise.append("M{:.1f} {:.1f}Q{:.1f} {:.1f} {:.1f} {:.1f}".format(*ends[0], *ends[1], *ends[2]))
    dots = "".join(f"M{rng.uniform(0, WIDTH):.1f} {rng.uniform(0, HEIGHT):.1f}h.1" for _ in range(40))
    return (
        f'<svg class="captcha" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        'role="img" aria-label="Verification characters" fill="none" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{"".join(noise)}" stroke="#8a7852" stroke-width="1.6"/>'
        f'<path d="{dots}" stroke="#8a7852" stroke-width="2.4"/>'
        f'<path d="{"".join(paths)}" stroke="#ece0c0" stroke-width="{rng.uniform(2.3, 3.1):.1f}"/>'
        "</svg>"
    )


class Captchas:
    """One-time challenges: a failed or successful answer uses the challenge up."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = Lock()
        self.pending = OrderedDict()
        self.random = secrets.SystemRandom()

    def issue(self):
        code = "".join(self.random.choice(ALPHABET) for _ in range(LENGTH))
        token = secrets.token_hex(16)
        now = self.clock()
        with self.lock:
            while self.pending and (len(self.pending) >= MAX_PENDING or next(iter(self.pending.values()))[1] <= now):
                self.pending.popitem(last=False)
            self.pending[token] = (code, now + LIFETIME)
        return token, draw(code, self.random)

    def verify(self, token, answer):
        with self.lock:
            entry = self.pending.pop(token, None)
        if entry is None or entry[1] <= self.clock():
            return False
        return hmac.compare_digest(entry[0].encode(), "".join(answer.split()).upper().encode())
