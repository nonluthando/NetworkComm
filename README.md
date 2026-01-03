# NetworkComm 
TCP Client–Server Chat Application

# Overview
This repository contains a Python-based TCP client–server chat application designed to demonstrate core networking, concurrency, and protocol-design concepts. 
The system enables multiple clients to connect to a central server and exchange messages in real time using socket programming and multithreading.

The server component was originally developed collaboratively as part of a group project, focusing on connection handling, concurrency control, and message routing.
Additional enhancements to the server were independently implemented, including structured message logging, improved error handling, clearer message formatting, and more robust coordination between clients.

The client component was independently implemented, handling user interaction, server communication, connection retry logic, and asynchronous message reception.

The project prioritises correctness, clarity, and real-world networking behaviour over UI complexity.

## Key Features
TCP socket–based communication
• Multithreaded server supporting multiple concurrent clients
Server-side enhancements:
• Structured logging of connections, disconnections, and message events
• Improved error handling for unexpected client disconnects
• Clear, timestamped message formatting
• Asynchronous message handling on the client side
• Simple, explicit text-based communication protocol
• Broadcast messaging, private messaging, and chat rooms
• User visibility controls (hide / reveal without disconnecting)
• Graceful client connection retries when the server is unavailable
• Clear separation between server and client responsibilities

## Architecture

1.	Server listens on a specified host and port
	2.	Clients connect and register with a nickname
	3.	Server spawns a dedicated handler thread per client
	4.	Messages are routed through the server (broadcast, private, or room-based)
	5.	Clients handle sending and receiving concurrently using separate threads

All communication is routed through the server to simplify coordination and maintain consistent state.

# Tech 
    • Language: Python
	• Networking: socket
	• Concurrency: threading
	• Encoding: utf-8
	• Environment: Localhost / LAN 

# Getting Started

Prerequisites
	•	Python 3.x
	•	Basic understanding of TCP networking

### Running the Server

python server.py
	•	The server will begin listening for incoming client connections

### Running the Client

python mbylut003_client.py

	•	Enter the server IP address and port ( default: 127.0.0.1, 44444)
	•	Provide a nickname when prompted
	•	Start sending messages once connected

Run multiple client instances to simulate concurrent users.


# Learning Outcomes

Learning Outcomes

This project demonstrates:
	•	Practical understanding of TCP/IP communication
	•	Concurrent programming using threads
	•	Client–server architecture and coordination
	•	Protocol design and synchronization
	•	Debugging and reasoning about networked systems
	•	Handling real-world issues such as connection ordering and message framing
	•	Collaborative development with clear component ownership
	•	Enhancing existing systems with logging, error handling, and maintainability improvements


## Notes
	•	This project prioritizes conceptual correctness and clarity over production-grade security.
	•	Authentication, encryption, and fault tolerance are intentionally out of scope.

## Limitations
	•	No authentication or access control: Users are identified only by nicknames, with no verification or protection against impersonation.
	•	No encryption: All messages are transmitted in plain text over TCP; confidentiality and integrity are not guaranteed.
	•	Implicit message framing: The protocol relies on command sequencing rather than explicit message delimiters or length-prefixed frames, which limits scalability and robustness.
	•	In-memory state only: Client connections, chat rooms, and visibility states are not persisted and are lost when the server shuts down.
	•	Single-server design: The system does not support horizontal scaling, load balancing, or fault tolerance.
	•	Terminal-based interface: The client uses a simple CLI, with no graphical user interface or rich interaction.
	•	Basic error recovery: While common network errors are handled gracefully, more advanced recovery strategies are not implemented.

## Future Enhancements
	•	Explicit protocol framing: Introduce length-prefixed or delimiter-based message framing to improve reliability and scalability.
	•	Authentication and authorization: Add user authentication and basic access controls for private messages and chat rooms.
	•	Encryption: Secure client–server communication using TLS or similar mechanisms.
	•	Persistent storage: Store user sessions, chat history, and room metadata using a database or file-based persistence.
	•	Improved scalability: Refactor the server to support asynchronous I/O or distributed architectures.
	•	Enhanced client experience: Add message alignment, richer formatting, or a graphical client interface.
	•	Configurable logging: Support log levels and output destinations (e.g. files, structured logs) for production-style monitoring.
	•	Testing and validation: Introduce automated tests for protocol handling, concurrency, and failure scenarios.
	
## Author Contributions
	•	Server: Group-developed as part of a networking coursework project, with independent enhancements including structured message logging, improved error handling, and message formatting
	•	Client & Documentation: Independently implemented and authored


