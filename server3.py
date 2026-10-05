"""TLS chat server: authenticated users, framed JSON protocol, rate limiting."""

import argparse
import logging
import re
import socket
import ssl
import threading
import time
from datetime import datetime

from auth import UserStore
from protocol import ProtocolError, recv_frame, send_frame

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chat-server")

ROOM_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")
MAX_TEXT = 2000
HANDSHAKE_TIMEOUT = 10     # seconds to complete the TLS handshake
AUTH_TIMEOUT = 30          # seconds to authenticate after connecting
IDLE_TIMEOUT = 900         # seconds of silence before dropping a session
MAX_AUTH_ATTEMPTS = 5
RATE_BURST = 10            # messages allowed in a burst
RATE_PER_SEC = 5           # sustained messages per second
MAX_VIOLATIONS = 10        # rate-limit hits before the connection is dropped


def clean_text(value):
    """Return value if it is a sane single-line string, else None.

    Control characters are refused so a user cannot inject terminal escape
    sequences into other users' consoles.
    """
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_TEXT:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value


class TokenBucket:
    def __init__(self, burst, per_sec):
        self.capacity = burst
        self.tokens = float(burst)
        self.per_sec = per_sec
        self.stamp = time.monotonic()

    def allow(self):
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.stamp) * self.per_sec)
        self.stamp = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class Session:
    def __init__(self, sock, address):
        self.sock = sock
        self.address = address
        self.nick = None
        self.hidden = False
        self.rooms = set()
        self._send_lock = threading.Lock()  # frames from many threads must not interleave

    def send(self, obj):
        try:
            with self._send_lock:
                send_frame(self.sock, obj)
            return True
        except (OSError, ProtocolError):
            return False

    def info(self, text):
        self.send({"type": "info", "text": text})

    def error(self, text):
        self.send({"type": "error", "text": text})


class Server:
    def __init__(self, host, port, certfile, keyfile, users_path="users.json", max_clients=100):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self.ctx.load_cert_chain(certfile, keyfile)

        self.users = UserStore(users_path)
        self.max_clients = max_clients
        self.lock = threading.Lock()
        self.sessions = {}   # lower-case username -> Session
        self.rooms = {}      # room name -> set of lower-case usernames
        self._count = 0
        self._closing = False

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen()
        self.host, self.port = self.listener.getsockname()[:2]

    # ---------------- accept loop ----------------

    def serve_forever(self):
        logger.info("Listening (TLS) on %s:%s", self.host, self.port)
        while not self._closing:
            try:
                conn, address = self.listener.accept()
            except OSError:
                break
            with self.lock:
                full = self._count >= self.max_clients
                if not full:
                    self._count += 1
            if full:
                logger.warning("Rejecting %s: server full", address[0])
                conn.close()
                continue
            threading.Thread(target=self._serve_client, args=(conn, address), daemon=True).start()

    def close(self):
        self._closing = True
        self.listener.close()

    # ---------------- per-connection ----------------

    def _serve_client(self, raw, address):
        session = None
        try:
            raw.settimeout(HANDSHAKE_TIMEOUT)
            try:
                sock = self.ctx.wrap_socket(raw, server_side=True)
            except (ssl.SSLError, OSError) as exc:
                logger.warning("TLS handshake failed from %s: %s", address[0], exc)
                raw.close()
                return
            session = Session(sock, address)
            sock.settimeout(AUTH_TIMEOUT)
            if not self._authenticate(session):
                return
            sock.settimeout(IDLE_TIMEOUT)
            self._announce(session, f"{session.nick} is online")
            logger.info("%s logged in from %s", session.nick, address[0])
            self._command_loop(session)
        except (ConnectionError, TimeoutError, ProtocolError, OSError) as exc:
            logger.info("Connection from %s ended: %s", address[0], exc)
        except Exception:
            logger.exception("Unhandled error for %s", address[0])
        finally:
            if session is not None:
                self._cleanup(session)
            else:
                raw.close()
            with self.lock:
                self._count -= 1

    def _authenticate(self, session):
        for _ in range(MAX_AUTH_ATTEMPTS):
            msg = recv_frame(session.sock)
            kind = msg.get("type")
            user, password = msg.get("user"), msg.get("password")
            if kind not in ("login", "register") or not isinstance(user, str) \
                    or not isinstance(password, str):
                session.error("Expected login or register")
                continue
            if kind == "register":
                err = self.users.register(user, password)
                if err:
                    session.error(err)
                    continue
                logger.info("Registered new user %s from %s", user, session.address[0])
            elif not self.users.verify(user, password):
                logger.warning("Failed login for %r from %s", user[:20], session.address[0])
                session.error("Invalid username or password")
                continue
            with self.lock:
                if user.lower() in self.sessions:
                    session.error("That user is already logged in")
                    continue
                session.nick = user
                self.sessions[user.lower()] = session
            session.send({"type": "auth_ok", "user": user})
            return True
        session.error("Too many attempts")
        return False

    def _command_loop(self, session):
        bucket = TokenBucket(RATE_BURST, RATE_PER_SEC)
        violations = 0
        while True:
            msg = recv_frame(session.sock)
            if not bucket.allow():
                violations += 1
                session.error("Slow down: rate limit exceeded")
                if violations >= MAX_VIOLATIONS:
                    logger.warning("Dropping %s for flooding", session.nick)
                    return
                continue
            handler = self.HANDLERS.get(msg.get("type"))
            if handler is None:
                session.error("Unknown command")
            elif handler(self, session, msg) == "quit":
                return

    # ---------------- helpers ----------------

    def _snapshot(self, nicks=None, exclude=None):
        with self.lock:
            sessions = self.sessions.values() if nicks is None else \
                [self.sessions[n] for n in nicks if n in self.sessions]
            return [s for s in sessions if s is not exclude]

    def _announce(self, session, text):
        for s in self._snapshot(exclude=session):
            s.info(f"Server: {text}")

    def _cleanup(self, session):
        with self.lock:
            if session.nick and self.sessions.get(session.nick.lower()) is session:
                del self.sessions[session.nick.lower()]
                for name in list(self.rooms):
                    self.rooms[name].discard(session.nick.lower())
            was_logged_in = session.nick is not None
        try:
            session.sock.close()
        except OSError:
            pass
        if was_logged_in:
            self._announce(session, f"{session.nick} is offline")
            logger.info("%s disconnected", session.nick)

    @staticmethod
    def _stamp():
        return datetime.now().strftime("%H:%M")

    # ---------------- commands ----------------

    def cmd_members(self, session, msg):
        with self.lock:
            users = sorted(s.nick for s in self.sessions.values() if not s.hidden)
        session.send({"type": "members", "users": users})

    def cmd_hide(self, session, msg):
        session.hidden = True
        session.info("You are now invisible!")

    def cmd_reveal(self, session, msg):
        session.hidden = False
        session.info("You are now visible to other users!")

    def cmd_broadcast(self, session, msg):
        text = clean_text(msg.get("text"))
        if text is None:
            return session.error("Invalid message")
        frame = {"type": "broadcast", "from": session.nick, "time": self._stamp(), "text": text}
        for s in self._snapshot(exclude=session):
            s.send(frame)
        session.info("Message broadcasted!")

    def cmd_dm(self, session, msg):
        text = clean_text(msg.get("text"))
        target = msg.get("to")
        if text is None or not isinstance(target, str):
            return session.error("Usage: dm <user> <message>")
        with self.lock:
            peer = self.sessions.get(target.lower())
        # hidden users answer exactly like absent ones, so hiding is not leaky
        if peer is None or peer.hidden:
            return session.error("User not found")
        peer.send({"type": "dm", "from": session.nick, "time": self._stamp(), "text": text})
        session.info("DM sent.")

    def cmd_create_room(self, session, msg):
        room = msg.get("room")
        if not isinstance(room, str) or not ROOM_RE.match(room):
            return session.error("Room names: 1-30 letters, digits, - or _")
        with self.lock:
            if room in self.rooms:
                return session.error(f"Room {room} already exists")
            self.rooms[room] = {session.nick.lower()}
            session.rooms.add(room)
        logger.info("%s created room %s", session.nick, room)
        session.info(f"Room {room} created successfully!")

    def cmd_join(self, session, msg):
        room = msg.get("room")
        with self.lock:
            members = self.rooms.get(room) if isinstance(room, str) else None
            if members is None:
                return session.error("Room does not exist")
            if session.nick.lower() in members:
                return session.error(f"You are already a member of {room}")
            members.add(session.nick.lower())
            session.rooms.add(room)
        session.info(f"Joined room {room} successfully!")

    def cmd_leave(self, session, msg):
        room = msg.get("room")
        with self.lock:
            members = self.rooms.get(room) if isinstance(room, str) else None
            if members is None or session.nick.lower() not in members:
                return session.error("Room does not exist or you are not a member")
            members.discard(session.nick.lower())
            session.rooms.discard(room)
        session.info(f"Left room {room}")

    def cmd_rooms(self, session, msg):
        with self.lock:
            names = sorted(self.rooms)
        session.send({"type": "rooms", "rooms": names})

    def cmd_room_msg(self, session, msg):
        room, text = msg.get("room"), clean_text(msg.get("text"))
        if text is None or not isinstance(room, str):
            return session.error("Invalid message")
        with self.lock:
            members = self.rooms.get(room)
            # authorisation: only members may post
            if members is None or session.nick.lower() not in members:
                return session.error("Room does not exist or you are not a member")
            targets = list(members)
        frame = {"type": "room_msg", "room": room, "from": session.nick,
                 "time": self._stamp(), "text": text}
        for s in self._snapshot(nicks=targets):
            s.send(frame)

    def cmd_quit(self, session, msg):
        session.send({"type": "bye"})
        return "quit"

    HANDLERS = {
        "members": cmd_members, "hide": cmd_hide, "reveal": cmd_reveal,
        "broadcast": cmd_broadcast, "dm": cmd_dm, "create_room": cmd_create_room,
        "join": cmd_join, "leave": cmd_leave, "rooms": cmd_rooms,
        "room_msg": cmd_room_msg, "quit": cmd_quit,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="TLS chat server")
    p.add_argument("host", nargs="?", default="127.0.0.1", help="address to bind")
    p.add_argument("port", nargs="?", type=int, default=44444, help="port to listen on")
    p.add_argument("--cert", default="certs/server.crt")
    p.add_argument("--key", default="certs/server.key")
    p.add_argument("--users", default="users.json", help="credential store path")
    args = p.parse_args()

    server = Server(args.host, args.port, args.cert, args.key, args.users)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down")
        server.close()
