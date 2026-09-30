import sys
import threading
import socket
import argparse
import logging
from datetime import datetime


# ---------------- LOGGING SETUP ----------------
# logging instead of print so we can actually trace what happens when things break

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("chat-server")


class Server:

    def __init__(self, host, port):

        self.host = host
        self.port = port
        self.FORMAT = 'utf-8'  # must match client

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen()

        self.clients = []      # active clients
        self.nicknames = []    # usernames of the active clients
        self.hidden = set()    # nicknames currently hidden from /members
        self.chatrooms = {}    # chatroom name -> list of members
        self.lock = threading.Lock()


    # modified so broadcasted message does not show to the client that sent the message
    def broadcast(self, message, this_client):

        message = message.encode(self.FORMAT)
        for client in self.clients:
            if client != this_client:
                try:
                    client.send(message)
                except OSError:
                    pass


    def handle(self, client):
        # get the nickname of the client
        nick = self.nicknames[self.clients.index(client)]

        while True:
            try:
                message = client.recv(1024)
                if not message:
                    raise ConnectionResetError
                decoded = message.decode(self.FORMAT)

                # list active members
                if decoded == "/members":
                    heading = "Active chat members are:\n"
                    names = ''

                    visible = [n for n in self.nicknames if n not in self.hidden]
                    for i, nickname in enumerate(visible, start=1):
                        names += f"{i}. {nickname}\n"

                    client.send((heading + names).encode(self.FORMAT))


                # Added option to appear anonymous and to stop appearing anonymous
                elif decoded == "/hide":
                    self.hidden.add(nick)
                    client.send('You are now invisible!'.encode(self.FORMAT))


                elif decoded == "/reveal":
                    self.hidden.discard(nick)
                    client.send('You are now visible to other users!'.encode(self.FORMAT))


                # added the option for clients to broadcast messages to other clients through the server
                elif decoded == "/broadcast":
                    client.send("Enter your message: ".encode(self.FORMAT))
                    client_msg = client.recv(1024).decode(self.FORMAT)

                    # WhatsApp-style formatting (timestamp + separation)
                    timestamp = datetime.now().strftime("%H:%M")
                    formatted_msg = (
                        f"\n──────────────\n"
                        f"{nick}  {timestamp}\n"
                        f"{client_msg}\n"
                        f"──────────────"
                    )

                    logger.info("Broadcast message", extra={"sender": nick})
                    self.broadcast(formatted_msg, client)
                    client.send("Message broadcasted!".encode(self.FORMAT))


                # create a new chatroom
                elif decoded.startswith("/create_room"):
                    room_name = decoded.split(" ")[1]

                    if room_name not in self.chatrooms:
                        self.chatrooms[room_name] = [client]
                        client.send(
                            f'Room {room_name} created successfully!'.encode(self.FORMAT))
                        logger.info("Created new chat room", extra={"room": room_name})
                    else:
                        client.send(
                            f'Room {room_name} already exists'.encode(self.FORMAT))


                # join chatroom
                elif decoded.startswith("/join"):
                    room_name = decoded.split(" ")[1]
                    if room_name in self.chatrooms:
                        if client not in self.chatrooms[room_name]:
                            self.chatrooms[room_name].append(client)
                            client.send(
                                f'Joined room {room_name} successfully!'.encode(self.FORMAT))
                            logger.info("Client joined room", extra={"room": room_name, "nickname": nick})
                        else:
                            client.send(
                                f'You are already a member of this room {room_name}.'.encode(self.FORMAT))
                    else:
                        client.send(
                            f'Room {room_name} does not exist!'.encode(self.FORMAT))


                # send message in chatroom
                elif decoded.startswith("/room"):
                    parts = decoded.split(" ")
                    room_name = parts[1]
                    broadcast_msg = " ".join(parts[2:])

                    if room_name in self.chatrooms:
                        timestamp = datetime.now().strftime("%H:%M")
                        formatted_msg = (
                            f"\n[{room_name} | {timestamp}]\n"
                            f"{nick}: {broadcast_msg}"
                        )

                        for member in self.chatrooms[room_name]:
                            member.send(formatted_msg.encode(self.FORMAT))
                    else:
                        client.send("Room does not exist".encode(self.FORMAT))


                # get a list of chatrooms
                elif decoded == "/get_rooms":
                    if len(self.chatrooms) == 0:
                        client.send("No rooms available".encode(self.FORMAT))
                    else:
                        rooms = "Rooms:\n" + "\n".join(self.chatrooms.keys())
                        client.send(rooms.encode(self.FORMAT))


                # leave the chatroom
                elif decoded.startswith("/leave"):
                    room_name = decoded.split(" ")[1]
                    if room_name in self.chatrooms and client in self.chatrooms[room_name]:
                        self.chatrooms[room_name].remove(client)
                        client.send(
                            f'Left room {room_name}'.encode(self.FORMAT))
                        logger.info("Client left room", extra={"room": room_name, "nickname": nick})
                    else:
                        client.send("Room does not exist or not a member".encode(self.FORMAT))


                # quit server connection
                elif decoded == "/quit":
                    logger.info("Client requested disconnect", extra={"nickname": nick})
                    client.send("Server: Bye".encode(self.FORMAT))
                    self.cleanup(client, nick)
                    break

                elif decoded.startswith("/dm"):
                    parts = decoded.split(" ", 2)
                    if len(parts) < 3:
                        client.send("Usage: /dm <user> <message>".encode(self.FORMAT))
                        continue
                    target_nick, dm_msg = parts[1], parts[2]
                    if target_nick in self.nicknames:
                        target_client = self.clients[self.nicknames.index(target_nick)]
                        timestamp = datetime.now().strftime("%H:%M")
                        formatted_msg = f"\n[DM | {timestamp}]\n{nick}: {dm_msg}"
                        target_client.send(formatted_msg.encode(self.FORMAT))
                        client.send("DM sent.".encode(self.FORMAT))
                    else:
                        client.send("User not found.".encode(self.FORMAT))


                else:
                    # server just listens without doing anything
                    # left here intentionally for future extensions
                    pass


            except ConnectionResetError:
                # client crashed or closed terminal without warning
                logger.warning("Client closed connection unexpectedly", extra={"nickname": nick})
                self.cleanup(client, nick)
                break


            except Exception:
                # catch-all for unexpected issues so the server keeps running
                logger.exception("Unhandled error in client handler", extra={"nickname": nick})
                self.cleanup(client, nick)
                break


    def cleanup(self, client, nick):
        # remove a client from all shared state, tolerating repeated calls
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)
                self.nicknames.remove(nick)
            self.hidden.discard(nick)
            for members in self.chatrooms.values():
                if client in members:
                    members.remove(client)
        try:
            self.broadcast(f"Server: {nick} is offline.", client)
        except OSError:
            pass
        client.close()


    def receive(self):
        logger.info("Server is on & listening on %s:%s", self.host, self.port)

        while True:
            try:
                client, address = self.server.accept()  # accept clients

                # receive nickname immediately after connection
                nickname = client.recv(1024).decode(self.FORMAT)

                self.nicknames.append(nickname)
                self.clients.append(client)

                logger.info("Connected with client", extra={"nickname": nickname, "address": address})

                # confirm successful connection to client
                client.send('Connected to the server'.encode(self.FORMAT))

                # notify other active clients
                self.broadcast(f"Server: {nickname} is online!", client)

                logger.info("Starting handler thread", extra={"nickname": nickname})
                thread = threading.Thread(target=self.handle, args=(client,))
                thread.start()

            except KeyboardInterrupt:
                # manual shutdown
                logger.info("Server shutting down")
                self.server.close()
                sys.exit()

            except Exception:
                # unrecoverable server-level error
                logger.exception("Fatal server error")
                self.server.close()
                sys.exit()


# ---------------- MAIN ----------------

if __name__ == "__main__":

    args = argparse.ArgumentParser(description="Server is on...")
    args.add_argument('host', nargs='?', type=str, default='127.0.0.1', help='Server IP address')
    args.add_argument('port', nargs='?', type=int, default=44444, help='Server port number')
    arguments = args.parse_args()

    # parse arguments to Server class
    server = Server(arguments.host, arguments.port)
    server.receive()  # start listening

