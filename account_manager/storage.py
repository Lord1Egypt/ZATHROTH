"""SQLite account operations shared by the browser and game login endpoints."""

from contextlib import closing, contextmanager
import ctypes
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3
import time
from xml.etree import ElementTree


ACCOUNT_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,31}")
EMAIL = re.compile(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+")
CHARACTER_NAME = re.compile(r"[a-zA-Z]+(?:[ '-][a-zA-Z]+)*")
STAFF_NAMES = {"admin", "administrator", "accountmanager", "cm", "gamemaster", "gm", "god"}
DAY = 86400
START_VOCATIONS = (1, 2, 3, 4, 9)
MAX_CHARACTERS = 20
# The shared 1/1 login opens this character. The game server keeps it still and
# never saves it; src/creatures/players/account_manager.cpp runs its dialog.
MANAGER_ACCOUNT = "1"
MANAGER_NAME = "Account Manager"


class AccountError(ValueError):
    """A user-facing account error."""


class Passwords:
    def __init__(self):
        self.library = ctypes.CDLL("libargon2.so.1")
        self.library.argon2id_hash_encoded.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t,
            ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t,
        ]
        self.library.argon2id_verify.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
        self.dummy = self.hash(secrets.token_hex(32))

    def hash(self, password):
        if not 8 <= len(password) <= 128 or any(c in password for c in "\x00\r\n"):
            raise AccountError("Use 8–128 characters for your password, without line breaks.")
        data = password.encode()
        salt = secrets.token_bytes(16)
        encoded = ctypes.create_string_buffer(255)
        result = self.library.argon2id_hash_encoded(
            2, 65536, 2, data, len(data), salt, len(salt), 32, encoded, len(encoded),
        )
        if result != 0:
            raise RuntimeError(f"Argon2 encoding failed with code {result}")
        return encoded.value.decode("ascii")

    def matches(self, password, stored_hash):
        if not 1 <= len(password) <= 128 or "\x00" in password:
            return False
        data = password.encode()
        if stored_hash and re.fullmatch(r"[a-fA-F0-9]{40}", stored_hash):
            return hmac.compare_digest(hashlib.sha1(data).hexdigest(), stored_hash.lower())
        encoded = stored_hash if stored_hash and stored_hash.startswith("$argon2id$") else self.dummy
        verified = self.library.argon2id_verify(encoded.encode(), data, len(data)) == 0
        return verified and encoded == stored_hash


class Accounts:
    def __init__(self, path, start_town, vocations_path):
        self.uri = Path(path).absolute().as_uri() + "?mode=rw"
        self.start_town = start_town
        self.passwords = Passwords()
        self.vocations = {
            int(vocation.attrib["id"]): vocation.attrib["name"]
            for vocation in ElementTree.parse(vocations_path).getroot().findall("vocation")
        }

    @contextmanager
    def connection(self, write=False):
        with closing(sqlite3.connect(self.uri, uri=True, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db

    def ready(self):
        with self.connection() as db:
            for table in ("accounts", "players", "players_online", "account_sessions"):
                db.execute(f"SELECT 1 FROM {table} LIMIT 1")
            return self.get_start_town(db) is not None

    def online_count(self):
        with self.connection() as db:
            return db.execute("SELECT count(*) FROM players_online").fetchone()[0]

    def boosted_races(self):
        with self.connection() as db:
            creature = db.execute("SELECT CAST(raceid AS INTEGER) FROM boosted_creature LIMIT 1").fetchone()
            boss = db.execute("SELECT CAST(raceid AS INTEGER) FROM boosted_boss LIMIT 1").fetchone()
            return (creature[0] if creature else 0), (boss[0] if boss else 0)

    def get_start_town(self, db):
        return db.execute(
            """
            SELECT id FROM towns WHERE posx > 0 AND posy > 0 AND (? = 0 OR id = ?)
            ORDER BY CASE WHEN name = 'Thais' COLLATE NOCASE THEN 0 ELSE 1 END, id LIMIT 1
            """,
            (self.start_town, self.start_town),
        ).fetchone()

    def authenticate(self, identifier, password):
        if not identifier:
            raise AccountError("Account or password is incorrect.")
        with self.connection() as db:
            # Accounts made in game have no email, so a blank email never matches.
            account = db.execute(
                "SELECT id, name, email, password, lastday FROM accounts WHERE name = ? OR (email <> '' AND email = ?) LIMIT 1",
                (identifier, identifier),
            ).fetchone()
        if not self.passwords.matches(password, account["password"] if account else None):
            raise AccountError("Account or password is incorrect.")
        return account

    def get(self, account_id):
        with self.connection() as db:
            return db.execute(
                "SELECT id, name, email, password, lastday FROM accounts WHERE id = ?", (account_id,),
            ).fetchone()

    def register(self, name, email, password):
        if not ACCOUNT_NAME.fullmatch(name):
            raise AccountError("Use 3–32 letters, digits, hyphens or underscores for the account name.")
        if len(email) > 255 or not EMAIL.fullmatch(email):
            raise AccountError("Enter a valid email address.")
        password_hash = self.passwords.hash(password)
        with self.connection(write=True) as db:
            if db.execute("SELECT 1 FROM accounts WHERE name = ? OR email = ?", (name, email)).fetchone():
                raise AccountError("That account name or email is already registered.")
            return db.execute(
                """
                INSERT INTO accounts (name, email, password, creation) VALUES (?, ?, ?, ?)
                RETURNING id, name, email, password, lastday
                """,
                (name, email, password_hash, int(time.time())),
            ).fetchone()

    def character_rows(self, db, account_id):
        return db.execute(
            """
            SELECT p.*, EXISTS (SELECT 1 FROM players_online WHERE player_id = p.id) AS online
            FROM players p WHERE p.account_id = ? ORDER BY p.name
            """,
            (account_id,),
        ).fetchall()

    def characters(self, account_id):
        with self.connection() as db:
            return self.character_rows(db, account_id)

    def ensure_current(self, db, account):
        if not db.execute(
            "SELECT 1 FROM accounts WHERE id = ? AND password = ?", (account["id"], account["password"]),
        ).fetchone():
            raise AccountError("Your session expired. Sign in again.")

    def create_character(self, account, name, sex, vocation):
        prefix = name.lower().split(" ", 1)[0]
        if (
            not 4 <= len(name) <= 29 or not CHARACTER_NAME.fullmatch(name)
            or prefix in STAFF_NAMES or name.lower() == "account manager"
        ):
            raise AccountError("Use an available fantasy name of 4–29 letters, with spaces, hyphens or apostrophes.")
        if sex not in (0, 1) or vocation not in START_VOCATIONS or vocation not in self.vocations:
            raise AccountError("Select an outfit and a vocation.")
        with self.connection(write=True) as db:
            self.ensure_current(db, account)
            if db.execute("SELECT 1 FROM players WHERE name = ?", (name,)).fetchone():
                raise AccountError("That character name is already in use.")
            count = db.execute("SELECT count(*) FROM players WHERE account_id = ?", (account["id"],)).fetchone()[0]
            if count >= MAX_CHARACTERS:
                raise AccountError(f"An account can have at most {MAX_CHARACTERS} characters.")
            town = self.get_start_town(db)
            if town is None:
                raise AccountError("No starting town is available. Check that the game server is ready.")
            db.execute(
                """
                INSERT INTO players (
                    name, account_id, level, vocation, experience, health, healthmax, mana, manamax,
                    soul, cap, town_id, conditions, sex, looktype, lookhead, lookbody, looklegs, lookfeet
                ) VALUES (?, ?, 8, ?, 4200, 185, 185, 90, 90, 100, 470, ?, X'', ?, ?, 78, 106, 116, 95)
                """,
                (name, account["id"], vocation, town["id"], sex, 128 if sex else 136),
            )

    def set_character_deletion(self, account, character_id, delete):
        now = int(time.time())
        with self.connection(write=True) as db:
            self.ensure_current(db, account)
            if delete:
                cursor = db.execute(
                    """
                    UPDATE players SET deletion = ? WHERE id = ? AND account_id = ? AND deletion = 0
                    AND NOT EXISTS (SELECT 1 FROM players_online WHERE player_id = players.id)
                    """,
                    (now + 7 * DAY, character_id, account["id"]),
                )
            else:
                cursor = db.execute(
                    "UPDATE players SET deletion = 0 WHERE id = ? AND account_id = ? AND deletion > ?",
                    (character_id, account["id"], now),
                )
            if cursor.rowcount != 1:
                raise AccountError("This character is unavailable for that action. Log out of the game before deleting.")

    def change_password(self, account, current, new):
        if not self.passwords.matches(current, account["password"]):
            raise AccountError("The current password is incorrect.")
        password_hash = self.passwords.hash(new)
        with self.connection(write=True) as db:
            self.ensure_current(db, account)
            updated = db.execute(
                "UPDATE accounts SET password = ? WHERE id = ? RETURNING id, name, email, password, lastday",
                (password_hash, account["id"]),
            ).fetchone()
            db.execute("DELETE FROM account_sessions WHERE account_id = ?", (account["id"],))
        return updated

    def ensure_manager(self, db):
        # The reserved account's empty password matches no hash, so only the
        # 1/1 shortcut in server.py can open it.
        account = db.execute(
            "SELECT id, name, email, password, lastday FROM accounts WHERE name = ?", (MANAGER_ACCOUNT,),
        ).fetchone() or db.execute(
            """
            INSERT INTO accounts (name, email, password, creation) VALUES (?, '', '', ?)
            RETURNING id, name, email, password, lastday
            """,
            (MANAGER_ACCOUNT, int(time.time())),
        ).fetchone()
        manager = db.execute("SELECT *, 0 AS online FROM players WHERE name = ?", (MANAGER_NAME,)).fetchone()
        if manager is None:
            town = self.get_start_town(db)
            if town is None:
                raise AccountError("The game server is still starting. Try again shortly.")
            manager = db.execute(
                """
                INSERT INTO players (
                    name, account_id, level, vocation, health, healthmax, mana, manamax,
                    cap, town_id, conditions, sex, looktype, lookhead, lookbody, looklegs, lookfeet
                ) VALUES (?, ?, 1, 0, 150, 150, 0, 0, 400, ?, X'', 1, 128, 78, 106, 116, 95)
                RETURNING *, 0 AS online
                """,
                (MANAGER_NAME, account["id"], town["id"]),
            ).fetchone()
        return account, manager

    def start_game_session(self, account=None):
        """Create a game session; with no account, for the shared 1/1 Account Manager."""
        key = secrets.token_hex(32)
        digest = hashlib.sha256(key.encode()).hexdigest()
        now = int(time.time())
        with self.connection(write=True) as db:
            manager_account, manager = self.ensure_manager(db)
            if account is None:
                account, characters = manager_account, []
            else:
                self.ensure_current(db, account)
                characters = [row for row in self.character_rows(db, account["id"]) if row["deletion"] == 0]
            characters.append(manager)
            db.execute("DELETE FROM account_sessions WHERE expires <= ?", (now,))
            db.execute(
                "INSERT INTO account_sessions (id, account_id, expires) VALUES (?, ?, ?)",
                (digest, account["id"], now + DAY),
            )
        return key, account, characters
