"""End-to-end tests: a real TLS server on an ephemeral port and real clients."""

import os
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import time
import unittest

import protocol
import server3
from auth import UserStore
from protocol import ProtocolError, recv_frame, send_frame


class Pipe:
    """Connected socket pair for framing tests."""
    def __enter__(self):
        self.a, self.b = socket.socketpair()
        return self.a, self.b

    def __exit__(self, *exc):
        self.a.close()
        self.b.close()


class FramingTests(unittest.TestCase):
    def test_roundtrip(self):
        with Pipe() as (a, b):
            send_frame(a, {"type": "x", "text": "héllo"})
            self.assertEqual(recv_frame(b), {"type": "x", "text": "héllo"})

    def test_coalesced_frames_stay_separate(self):
        with Pipe() as (a, b):
            send_frame(a, {"n": 1})
            send_frame(a, {"n": 2})
            self.assertEqual(recv_frame(b)["n"], 1)
            self.assertEqual(recv_frame(b)["n"], 2)

    def test_oversized_length_rejected(self):
        with Pipe() as (a, b):
            a.sendall(struct.pack(">I", protocol.MAX_FRAME + 1))
            with self.assertRaises(ProtocolError):
                recv_frame(b)

    def test_malformed_json_rejected(self):
        with Pipe() as (a, b):
            a.sendall(struct.pack(">I", 3) + b"{{{")
            with self.assertRaises(ProtocolError):
                recv_frame(b)

    def test_non_object_rejected(self):
        with Pipe() as (a, b):
            a.sendall(struct.pack(">I", 2) + b"[]")
            with self.assertRaises(ProtocolError):
                recv_frame(b)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = UserStore(os.path.join(self.dir, "u.json"))

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_register_and_verify(self):
        self.assertIsNone(self.store.register("alice", "correct horse"))
        self.assertTrue(self.store.verify("alice", "correct horse"))
        self.assertFalse(self.store.verify("alice", "wrong password"))
        self.assertFalse(self.store.verify("nobody", "correct horse"))

    def test_password_not_stored_in_plaintext_and_salted(self):
        self.store.register("alice", "correct horse")
        self.store.register("bobby", "correct horse")
        raw = open(self.store.path).read()
        self.assertNotIn("correct horse", raw)
        self.assertNotEqual(self.store._users["alice"]["hash"], self.store._users["bobby"]["hash"])

    def test_store_file_is_private(self):
        self.store.register("alice", "correct horse")
        self.assertEqual(os.stat(self.store.path).st_mode & 0o777, 0o600)

    def test_persists_across_restart(self):
        self.store.register("alice", "correct horse")
        again = UserStore(self.store.path)
        self.assertTrue(again.verify("alice", "correct horse"))

    def test_validation(self):
        self.assertIsNotNone(self.store.register("a b", "correct horse"))
        self.assertIsNotNone(self.store.register("alice", "short"))
        self.store.register("alice", "correct horse")
        self.assertIsNotNone(self.store.register("ALICE", "correct horse"))

    def test_lockout_after_repeated_failures(self):
        self.store.register("alice", "correct horse")
        for _ in range(5):
            self.assertFalse(self.store.verify("alice", "nope nope"))
        # even the right password is refused while locked
        self.assertFalse(self.store.verify("alice", "correct horse"))


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        crt, key = os.path.join(cls.dir, "s.crt"), os.path.join(cls.dir, "s.key")
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-keyout", key, "-out", crt, "-subj", "/CN=localhost",
             "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
            check=True, capture_output=True)
        cls.crt = crt
        cls.server = server3.Server("127.0.0.1", 0, crt, key, os.path.join(cls.dir, "u.json"))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        shutil.rmtree(cls.dir)

    def setUp(self):
        self.socks = []

    def tearDown(self):
        for s in self.socks:
            s.close()

    def connect(self):
        ctx = ssl.create_default_context(cafile=self.crt)
        s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", self.server.port)),
                            server_hostname="127.0.0.1")
        s.settimeout(5)
        self.socks.append(s)
        return s

    def user(self, name, password="correct horse"):
        s = self.connect()
        send_frame(s, {"type": "register", "user": name, "password": password})
        self.assertEqual(recv_frame(s)["type"], "auth_ok")
        return s

    def ask(self, s, **msg):
        send_frame(s, msg)
        return recv_frame(s)


class ServerTests(ServerTestCase):
    def test_login_wrong_password_rejected(self):
        self.user("loginuser")
        s = self.connect()
        reply = self.ask(s, type="login", user="loginuser", password="not the password")
        self.assertEqual(reply["type"], "error")

    def test_commands_require_authentication(self):
        s = self.connect()
        reply = self.ask(s, type="broadcast", text="hi")
        self.assertEqual(reply["type"], "error")

    def test_duplicate_session_rejected(self):
        self.user("dupuser")
        s = self.connect()
        reply = self.ask(s, type="login", user="dupuser", password="correct horse")
        self.assertEqual(reply["type"], "error")

    def test_dm_delivered(self):
        a, b = self.user("dm_alice"), self.user("dm_bob")
        recv_frame(a)  # "dm_bob is online"
        self.assertEqual(self.ask(a, type="dm", to="dm_bob", text="hi")["text"], "DM sent.")
        got = recv_frame(b)
        self.assertEqual((got["type"], got["from"], got["text"]), ("dm", "dm_alice", "hi"))

    def test_sender_name_comes_from_login_not_message(self):
        a, b = self.user("spoof_a"), self.user("spoof_b")
        recv_frame(a)
        send_frame(a, {"type": "dm", "to": "spoof_b", "text": "x", "from": "admin"})
        recv_frame(a)
        self.assertEqual(recv_frame(b)["from"], "spoof_a")

    def test_hidden_user_indistinguishable_from_absent(self):
        a, b = self.user("hid_a"), self.user("hid_b")
        recv_frame(a)
        self.ask(b, type="hide")
        hidden = self.ask(a, type="dm", to="hid_b", text="hi")
        absent = self.ask(a, type="dm", to="hid_nobody", text="hi")
        self.assertEqual(hidden, absent)
        self.assertNotIn("hid_b", self.ask(a, type="members")["users"])

    def test_room_post_requires_membership(self):
        a, b = self.user("room_a"), self.user("room_b")
        recv_frame(a)
        self.assertIn("created", self.ask(a, type="create_room", room="lobby1")["text"])
        denied = self.ask(b, type="room_msg", room="lobby1", text="let me in")
        self.assertEqual(denied["type"], "error")
        self.ask(b, type="join", room="lobby1")
        send_frame(b, {"type": "room_msg", "room": "lobby1", "text": "hello"})
        self.assertEqual(recv_frame(a)["text"], "hello")

    def test_control_characters_refused(self):
        a = self.user("ctl_a")
        reply = self.ask(a, type="broadcast", text="\x1b[2Jboom")
        self.assertEqual(reply["type"], "error")

    def test_bad_room_name_refused(self):
        a = self.user("badroom")
        self.assertEqual(self.ask(a, type="create_room", room="../etc")["type"], "error")

    def test_malformed_types_do_not_crash_server(self):
        a = self.user("fuzz_a")
        for bad in ({"type": "dm", "to": 5, "text": 5}, {"type": "join", "room": ["x"]},
                    {"type": "room_msg"}, {"type": None}, {}):
            self.assertEqual(self.ask(a, **bad)["type"], "error")
        self.assertEqual(self.ask(a, type="members")["type"], "members")

    def test_rate_limit(self):
        a = self.user("flood_a")
        for _ in range(14):  # burst allowance is 10; stays under the disconnect threshold
            send_frame(a, {"type": "members"})
        replies = [recv_frame(a) for _ in range(14)]
        self.assertTrue(any(r["type"] == "error" and "rate" in r["text"] for r in replies))

    def test_sustained_flooding_disconnects(self):
        a = self.user("flood_b")
        try:
            for _ in range(200):
                send_frame(a, {"type": "members"})
        except OSError:
            pass
        a.settimeout(5)
        with self.assertRaises((ConnectionError, OSError)):
            while True:
                recv_frame(a)

    def test_oversized_frame_drops_connection(self):
        a = self.user("big_a")
        a.sendall(struct.pack(">I", 10 * 1024 * 1024))
        with self.assertRaises((ConnectionError, OSError)):
            recv_frame(a)


class TransportSecurityTests(ServerTestCase):
    def test_plaintext_client_gets_nothing(self):
        s = socket.create_connection(("127.0.0.1", self.server.port), timeout=5)
        send_frame(s, {"type": "register", "user": "plain1", "password": "correct horse"})
        try:
            data = s.recv(1024)
        except OSError:
            data = b""
        s.close()
        self.assertNotIn(b"auth_ok", data)

    def test_untrusted_certificate_rejected(self):
        ctx = ssl.create_default_context()  # system trust store; our cert is self-signed
        raw = socket.create_connection(("127.0.0.1", self.server.port), timeout=5)
        with self.assertRaises(ssl.SSLCertVerificationError):
            ctx.wrap_socket(raw, server_hostname="127.0.0.1")
        raw.close()

    def test_hostname_mismatch_rejected(self):
        ctx = ssl.create_default_context(cafile=self.crt)
        raw = socket.create_connection(("127.0.0.1", self.server.port), timeout=5)
        with self.assertRaises(ssl.SSLCertVerificationError):
            ctx.wrap_socket(raw, server_hostname="evil.example")
        raw.close()

    def test_old_tls_versions_refused(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.maximum_version = ssl.TLSVersion.TLSv1_1
        except (ValueError, ssl.SSLError):
            self.skipTest("TLS 1.1 not available in this OpenSSL build")
        raw = socket.create_connection(("127.0.0.1", self.server.port), timeout=5)
        with self.assertRaises(ssl.SSLError):
            ctx.wrap_socket(raw)
        raw.close()


if __name__ == "__main__":
    unittest.main()
