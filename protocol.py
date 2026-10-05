"""Wire protocol shared by the server and client.

Every message is a frame: a 4-byte big-endian length followed by that many
bytes of UTF-8 JSON (a single JSON object). Length-prefixing gives explicit
message boundaries, so TCP segmentation/coalescing cannot merge or split
messages, and the length cap bounds how much memory a peer can make us allocate.
"""

import json
import struct

MAX_FRAME = 16 * 1024  # bytes; frames larger than this are rejected


class ProtocolError(Exception):
    """The peer sent something that is not a valid frame."""


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return bytes(buf)


def send_frame(sock, obj):
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ProtocolError("frame too large")
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_frame(sock):
    (length,) = struct.unpack(">I", recv_exact(sock, 4))
    if length == 0 or length > MAX_FRAME:
        raise ProtocolError(f"invalid frame length {length}")
    try:
        obj = json.loads(recv_exact(sock, length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("malformed JSON") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("frame must be a JSON object")
    return obj
