import socket
import threading

COMMANDS = {
    "MEMBERS": "/members",
    "BROADCAST": "/broadcast",
    "HIDE": "/hide",
    "REVEAL": "/reveal",
    "CREATE_ROOM": "/create_room",
    "GET_ROOMS": "/get_rooms",
    "JOIN": "/join",
    "LEAVE": "/leave",
    "ROOM": "/room"
}

def receive(client_sock):
    while True:
        try:
            data = client_sock.recv(1024)
            if not data:
                break
            print(data.decode("ascii"))
        except OSError:
            break

def send(client_sock, msg):
    client_sock.send(msg.encode("ascii"))

def main():
    host = input("Enter server IP address: ")
    port = int(input("Enter server port number: "))
    nickname = input("Enter your nickname: ")

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect((host, port))

    send(client_sock, nickname)

    receive_thread = threading.Thread(
        target=receive, args=(client_sock,), daemon=True
    )
    receive_thread.start()

    while True:
        print('Select an option from the menu:')
        menu = """
                 a. view list of available users
                 b. send message to all connected users
                 c. hide your connection 
                 d. reveal
                 e. create a new chatroom 
                 f. get list of existing chatrooms
                 g. join a chatroom
                 h. send a message in a chatroom
                 i. exit a chatroom
                 j. quit \n"""
        choice = input(menu).strip().lower()

        if choice == "a":
            send(client_sock, COMMANDS["MEMBERS"])

        elif choice == "b":
            send(client_sock, COMMANDS["BROADCAST"])
            msg = input()
            send(client_sock, msg)

        elif choice == "c":
            send(client_sock, COMMANDS["HIDE"])

        elif choice == "d":
            send(client_sock, COMMANDS["REVEAL"])

        elif choice == "e":
            chatname = input("Please enter the name you want to give your chatroom: \n")
            send(client_sock, f"{COMMANDS['CREATE_ROOM']} {chatname}")

        elif choice == "f":
            send(client_sock, COMMANDS["GET_ROOMS"])

        elif choice == "g":
            chatname = input("Please enter the name you want to join: \n")
            send(client_sock, f"{COMMANDS['JOIN']} {chatname}")

        elif choice == "h":
            chatname = input("Please enter the name you want to send message to: \n")
            txt = input("Please enter your message: \n")
            send(client_sock, f"{COMMANDS['ROOM']} {chatname} {txt}")

        elif choice == "i":
            chatname = input("Please enter the name you want to exit: \n")
            send(client_sock, f"{COMMANDS['LEAVE']} {chatname}")

        elif choice == "j":
            print("Disconnecting...")
            client_sock.close()
            break

        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()
