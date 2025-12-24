import sys
import threading
import socket
import argparse


class Server:

    def __init__(self, host, port):

        self.host = host
        self.port = port
        self.FORMAT = 'ascii'

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen()

        self.clients = []      # active clients
        self.nicknames = []    # usernames of the active clients
        self.chatrooms = {}  # chatroom stores tcp addr and port and list of members

    # modified so broadcasted message dooes not show to the client that sent the message
    def broadcast(self, message, this_client):

        message = message.encode(self.FORMAT)
        for client in self.clients:
            if client != this_client:
                client.send(message)

    def handle(self, client):
        # get the nickname of the client
        nick = self.nicknames[self.clients.index(client)]

        while True:
            try:
                message = client.recv(1024)

                if message.decode(self.FORMAT) == "/members":
                    heading = "Active chat members are:\n"
                    names = ''

                    for i, nickname in enumerate(self.nicknames, start=1):
                        names += f"{i}.{nickname}: {self.clients[i-1].getpeername()}"

                    
                    client.send(f"{heading} {names}\n".encode(self.FORMAT))

                # Added option to appear anonymous and to stop appearing anonymous
                elif message.decode(self.FORMAT).startswith("/hide"):
                    # Get the nickname of the client that sent the prompt
                    # Prompt client to send nickname
                    client.send('Enter nickname to hide'.encode(self.FORMAT))
                    nickname_to_remove = client.recv(1024).decode(self.FORMAT)

                    # remove nickname from the list
                    self.nicknames.remove(nickname_to_remove)
                    client.send('You are now invisible!'.encode(self.FORMAT))  #server informs client they've been removed from visible clients
                elif message.decode(self.FORMAT).startswith("/reveal"):
                    # Prompt client to send nickname
                    client.send('Enter nickname to show'.encode(self.FORMAT))
                    nickname_to_add = client.recv(1024).decode(self.FORMAT)

                    if nickname_to_add in self.nicknames:
                        continue  # nickname already there, no need to re-add it
                    else:
                        self.nicknames.append(nickname_to_add)
                        client.send('You are now visible to other users!'.encode(self.FORMAT))  #server informs client they've been added to visible clients' list

                # added the option for clients to broadcast messages to other clients through the server
                elif message.decode(self.FORMAT) == "/broadcast":
                    client.send("Enter your message: ".encode(self.FORMAT))
                    client_msg = client.recv(1024).decode(self.FORMAT)
                    broad_msg = f"{nick}: {client_msg}"

                    self.broadcast(broad_msg, client)
                    client.send("Message broadcasted!".encode(self.FORMAT))

                elif message.decode(self.FORMAT).startswith("/create_room"):  # create a new room
                    room_name = message.decode(self.FORMAT).split(" ")[1]

                    if room_name not in self.chatrooms:
                        self.chatrooms[room_name] = [client]
                        client.send(
                            f'Room {room_name} created successfully!'.encode(self.FORMAT))
                        print("Created new chat room ", room_name)
                    else:
                        client.send(
                            f'Room {room_name} already exists'.encode(self.FORMAT))
                        print("{room_name} already exists ")

                elif message.decode(self.FORMAT).startswith("/join"):  # join chatroom
                    room_name = message.decode(self.FORMAT).split(" ")[1]
                    if room_name in self.chatrooms:
                        if client not in self.chatrooms[room_name]:
                            self.chatrooms[room_name].append(client)
                            client.send(
                                f'Joined room {room_name} successfully!'.encode(self.FORMAT))
                            print(f"{client} joined room ", room_name)
                        else:
                            client.send(
                                f'You are already a member of this room {room_name}.'.encode(self.FORMAT))
                            print(f"{client} aleady a member of ", room_name)

                    else:
                        client.send(
                            f'Room {room_name} does not exist!'.encode(self.FORMAT))

                # send message in chatroom
                elif message.decode(self.FORMAT).startswith("/room"):
                    parts = message.decode(self.FORMAT).split(" ")
                    room_name = parts[1]
                    broadcast_msg_parts = parts[2:]
                    broadcast_msg = " ".join(broadcast_msg_parts)

                    if room_name in self.chatrooms:
                        members = self.chatrooms[room_name]

                        for member in members:
                            member.send(broadcast_msg.encode(self.FORMAT))
                        print("Message broadcasted to members of ", room_name)
                    
                    else:
                        client.send("Room does not exist".encode(self.FORMAT))

                elif message.decode(self.FORMAT) == "/get_rooms":  # get a list of chatrooms
                    heading = "Rooms:\n"
                    rooms = ''
                    if len(self.chatrooms) == 0:
                        client.send("No rooms available".encode(self.FORMAT))
                    
                    else:

                        for room, _ in self.chatrooms.items():
                            rooms = rooms + room + "  "
                        room_list = heading + rooms

                        client.send(room_list.encode(self.FORMAT))
                        print("Send a list of rooms to ", client)

                elif message.decode(self.FORMAT).startswith("/leave"):  # leave the chatroom
                    room_name = message.decode(self.FORMAT).split(" ")[1]
                    members = self.chatrooms[room_name]
                    if room_name in self.chatrooms:
                        if client in members:
                            self.chatrooms[room_name].remove(client)
                            client.send(
                                f'Left room {room_name}'.encode(self.FORMAT))
                            print(f"{client} left room ", room_name)
                        else:
                            client.send(
                                f'You are not a member of room {room_name}'.encode(self.FORMAT))
                    else:
                        client.send("Room does not exist".encode(self.FORMAT))
                
                elif message.decode(self.FORMAT) == "/quit":  # quit server connection
                    client.send("Server: Bye".encode(self.FORMAT))
                    print(f"Closed connection: {nick}")
                    self.broadcast(f"{nick} is offline", client)

                    self.clients.remove(client)
                    self.nicknames.remove(nick)
                    client.close()
 
                else:
                    # server just listens without doing anything (might be used later for reliability idk)
                    pass

            except ConnectionResetError:
                print("Client closed connection unexpectedly.")
                self.broadcast(f"Server: {nick} is offline.\n", client)

                self.clients.remove(client)
                self.nicknames.remove(nick)
                break

            except Exception as e:
                client.send(e.encode(self.FORMAT)) # send exception info to client

                print(f"Closed connection: {nick}")
                self.broadcast(f"{nick} is offline", client)

                self.clients.remove(client)
                self.nicknames.remove(nick)
                client.close()
                break

    def receive(self):
        print("Server is on & listening...")

        while True:
            try:
                client, address = self.server.accept()  # accept clients
                # Note in your client implementation -- just send the nickname without having to check for prompt.
                # Receive nickname, then apppend this nickname and client to our lists
                nickname = client.recv(1024).decode(self.FORMAT)

                print(f'Connected with [{nickname}: {address}]')

                self.nicknames.append(nickname)
                self.clients.append(client)

                # Send the message to this particular client that the connection was successful
                client.send('Connected to the server'.encode(self.FORMAT))
                # broadcast to active members that said client is online
                self.broadcast(f"Server: {nickname} is online!", client)

                thread = threading.Thread(target=self.handle, args=(client,))
                thread.start()

            except OSError as e:
                print("Socket error occurred:", e)
                print("Attempting to recover...")
                self.server.close()

                # Re-initialize server socket
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.bind((self.host, self.port))
                self.server.listen()

                print("Server reinitialized.")

            except KeyboardInterrupt as e:
                print(e)
                self.server.close()
                break

            except Exception as e:
                # unrecoverable case
                self.server.close()
                print("Error: ", str(e))
                sys.exit()


if __name__ == "__main__":  # main method

    args = argparse.ArgumentParser(description="Server is on...")
    args.add_argument('host', nargs='?', type=str,default='127.0.0.1', help='Server IP address')
    args.add_argument('port', nargs='?', type=int, default=44444, help='Server port number')
    arguments = args.parse_args()

    # parse arguments to Server class
    server = Server(arguments.host, arguments.port)
    server.receive()  # calling the receive function

