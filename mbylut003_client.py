import argparse
import getpass
import socket
import ssl
import threading
import time

from protocol import ProtocolError, recv_frame, send_frame


def show(msg):
    """Render one server frame."""
    kind = msg.get("type")
    if kind == "broadcast":
        print(f"\n──────────────\n{msg['from']}  {msg['time']}\n{msg['text']}\n──────────────")
    elif kind == "dm":
        print(f"\n[DM | {msg['time']}]\n{msg['from']}: {msg['text']}")
    elif kind == "room_msg":
        print(f"\n[{msg['room']} | {msg['time']}]\n{msg['from']}: {msg['text']}")
    elif kind == "members":
        print("Active chat members are:")
        for i, name in enumerate(msg["users"], start=1):
            print(f"{i}. {name}")
    elif kind == "rooms":
        print(("Rooms:\n" + "\n".join(msg["rooms"])) if msg["rooms"] else "No rooms available")
    elif kind == "error":
        print(f"Error: {msg['text']}")
    elif kind == "bye":
        print("Server: Bye")
    else:
        print(msg.get("text", ""))


def receive(sock):
    # continuously listen for server messages
    while True:
        try:
            show(recv_frame(sock))
        except (OSError, ProtocolError):
            break


def connect(host, port, cafile, attempts=5):
    # the context verifies the server certificate and hostname; it is never disabled
    ctx = ssl.create_default_context(cafile=cafile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    for attempt in range(1, attempts + 1):
        try:
            raw = socket.create_connection((host, port), timeout=10)
        except OSError:
            print(f"Server unavailable, retrying ({attempt}/{attempts})...")
            time.sleep(2)
            continue
        try:
            sock = ctx.wrap_socket(raw, server_hostname=host)
        except ssl.SSLError as exc:
            raw.close()
            print(f"TLS verification failed: {exc}")
            return None
        sock.settimeout(None)
        return sock
    print("Could not connect to the server.")
    return None


def authenticate(sock):
    while True:
        mode = input("(l)ogin or (r)egister? ").strip().lower()
        if mode not in ("l", "r"):
            continue
        user = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        send_frame(sock, {"type": "login" if mode == "l" else "register",
                          "user": user, "password": password})
        reply = recv_frame(sock)
        if reply.get("type") == "auth_ok":
            print(f"Logged in as {reply['user']}")
            return True
        print(f"Error: {reply.get('text', 'authentication failed')}")


MENU = """
                 a. view list of available users
                 b. send message to all connected users
                 c. hide your connection
                 d. reveal
                 e. create a new chatroom
                 f. get list of existing chatrooms
                 g. join a chatroom
                 h. send a message in a chatroom
                 i. exit a chatroom
                 j. quit
                 k. send a direct message
"""


def main():
    p = argparse.ArgumentParser(description="TLS chat client")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=44444)
    p.add_argument("--cafile", default="certs/server.crt",
                   help="certificate to trust (the server's, for self-signed setups)")
    args = p.parse_args()

    sock = connect(args.host, args.port, args.cafile)
    if sock is None:
        return
    try:
        authenticate(sock)
    except (OSError, ProtocolError) as exc:
        print(f"Connection lost during login: {exc}")
        return

    threading.Thread(target=receive, args=(sock,), daemon=True).start()

    try:
        while True:
            print("Select an option from the menu:")
            choice = input(MENU).strip().lower()

            if choice == "a":
                send_frame(sock, {"type": "members"})
            elif choice == "b":
                send_frame(sock, {"type": "broadcast", "text": input("Message: ")})
            elif choice == "c":
                send_frame(sock, {"type": "hide"})
            elif choice == "d":
                send_frame(sock, {"type": "reveal"})
            elif choice == "e":
                send_frame(sock, {"type": "create_room", "room": input("Room name:\n")})
            elif choice == "f":
                send_frame(sock, {"type": "rooms"})
            elif choice == "g":
                send_frame(sock, {"type": "join", "room": input("Room to join:\n")})
            elif choice == "h":
                room = input("Room to send to:\n")
                send_frame(sock, {"type": "room_msg", "room": room, "text": input("Message:\n")})
            elif choice == "i":
                send_frame(sock, {"type": "leave", "room": input("Room to leave:\n")})
            elif choice == "k":
                user = input("Nickname to message:\n")
                send_frame(sock, {"type": "dm", "to": user, "text": input("Message:\n")})
            elif choice == "j":
                print("Disconnecting...")
                send_frame(sock, {"type": "quit"})
                break
            else:
                print("Invalid option. Please try again.")
    except (OSError, ProtocolError) as exc:
        print(f"Connection lost: {exc}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
