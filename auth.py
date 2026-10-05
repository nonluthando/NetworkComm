"""Credential storage: salted scrypt hashes in a JSON file, plus lockout."""

import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128

# scrypt cost parameters (~16 MiB, tens of ms per hash)
_N, _R, _P = 2 ** 14, 8, 1

MAX_FAILURES = 5
LOCKOUT_SECONDS = 60


def _hash(password, salt):
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P)


class UserStore:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._failures = {}  # username -> (count, locked_until)
        self._users = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._users = json.load(f)
        # verifying an unknown user still costs one scrypt run, so response
        # time does not reveal whether a username exists
        self._dummy_salt = os.urandom(16)

    def _save(self):
        tmp = self.path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._users, f)
        os.replace(tmp, self.path)

    def register(self, username, password):
        """Return None on success or an error string."""
        if not USERNAME_RE.match(username):
            return "Username must be 3-20 characters: letters, digits, underscore"
        if not MIN_PASSWORD_LEN <= len(password) <= MAX_PASSWORD_LEN:
            return f"Password must be {MIN_PASSWORD_LEN}-{MAX_PASSWORD_LEN} characters"
        salt = os.urandom(16)
        digest = _hash(password, salt)
        key = username.lower()
        with self._lock:
            if key in self._users:
                return "Username already taken"
            self._users[key] = {
                "salt": base64.b64encode(salt).decode(),
                "hash": base64.b64encode(digest).decode(),
            }
            self._save()
        return None

    def locked(self, username):
        with self._lock:
            _, until = self._failures.get(username.lower(), (0, 0))
            return until > time.monotonic()

    def verify(self, username, password):
        key = username.lower()
        if self.locked(key):
            return False
        with self._lock:
            record = self._users.get(key)
        if record:
            salt = base64.b64decode(record["salt"])
            expected = base64.b64decode(record["hash"])
        else:
            salt, expected = self._dummy_salt, b"\0" * 64
        ok = hmac.compare_digest(_hash(password, salt), expected) and record is not None
        with self._lock:
            if ok:
                self._failures.pop(key, None)
            else:
                count, _ = self._failures.get(key, (0, 0))
                count += 1
                until = time.monotonic() + LOCKOUT_SECONDS if count >= MAX_FAILURES else 0
                self._failures[key] = (0 if until else count, until)
        return ok
