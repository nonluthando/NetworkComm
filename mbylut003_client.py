import socket
import threading

def receive(client_sock):
    while True:
        try:
            message = client_sock.recv(1024).decode('ascii')
            print(message)
        except ConnectionAbortedError:
            break
#convert menu options to messages forr server

def main():
    host = input("Enter server IP address: ")
    port = int(input("Enter server port number: "))
    nickname = input("Enter your nickname: ")

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect((host, port))

    # Send nickname to the server
    client_sock.send(nickname.encode('ascii'))

    # Start a thread to receive messages from the server
    receive_thread = threading.Thread(target=receive, args=(client_sock,))
    receive_thread.start()
    
    

    while True:
        print('Select an option from the menu:')
        menu="""
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
        message = input(menu)
        if message == "a":
            msg="/members"
            client_sock.send(msg.encode('ascii'))
        elif message == "b":
             msg="/broadcast"
             client_sock.send(msg.encode('ascii'))
             msg = input()
             client_sock.send(msg.encode('ascii'))
        elif message == "c":
             msg="/hide"
             client_sock.send(msg.encode('ascii'))
             msg = input()
             client_sock.send(msg.encode('ascii'))
        elif message == "d":
             msg="/reveal"
             client_sock.send(msg.encode('ascii'))
             msg = input()
             client_sock.send(msg.encode('ascii'))
        elif message == "e":
            chatname=input("Please enter the name you want to give your chatroom: \n")
            msg="/create_room "+chatname
            client_sock.send(msg.encode('ascii'))
            msg = input()
            client_sock.send(msg.encode('ascii'))
        elif message == "g":
            chatname=input("Please enter the name you want to join: \n")
            msg="/join "+chatname
            client_sock.send(msg.encode('ascii'))
            msg = input()
            client_sock.send(msg.encode('ascii'))
        elif message == "f":
             msg = "/get_rooms "
             client_sock.send(msg.encode('ascii'))
        elif message == "i":
            chatname=input("Please enter the name you want to exit: \n")
            msg="/leave "+chatname
            client_sock.send(msg.encode('ascii'))
            msg = input()
            client_sock.send(msg.encode('ascii'))
        elif message == "h":
             chatname=input("Please enter the name you want to send message to: \n")
             txt= input("Please enter your message: \n")             
             msg="/room "+chatname+" "+txt
             client_sock.send(msg.encode('ascii'))
             msg = input()
             client_sock.send(msg.encode('ascii'))   
    

    client_sock.close()

if __name__ == "__main__":
    main()

    
    