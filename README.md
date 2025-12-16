# NetworkComm 
TCP Client–Server Chat Application

Overview

This repository contains a Python-based TCP client–server chat application designed to demonstrate core networking and concurrency concepts.
The system enables multiple clients to connect to a central server and exchange messages in real time using socket programming and multithreading.

The server component was developed collaboratively as part of a group project, focusing on connection handling, message broadcasting, and concurrency control.
The client component was independently implemented, handling user interaction, server communication, and asynchronous message reception.

⸻

Key Features
	•	TCP socket-based communication
	•	Multithreaded server supporting multiple concurrent clients
	•	Asynchronous message handling on the client side
	•	Simple text-based communication protocol
	•	Clear separation between server and client responsibilities
	•	Structured documentation and accompanying technical report

⸻

Architecture

High-level flow:
	1.	Server listens on a specified host and port
	2.	Clients connect and register with a nickname
	3.	Server spawns a new thread per client
	4.	Messages are received and broadcast to all connected clients
	5.	Clients handle sending and receiving concurrently

⸻

Tech Stack
	•	Language: Python
	•	Networking: socket
	•	Concurrency: threading
	•	Environment: Localhost / LAN 

⸻

Getting Started

Prerequisites
	•	Python 3.x
	•	Basic understanding of TCP networking

Running the Server

python server.py

	•	Specify the host and port when prompted
	•	The server will begin listening for incoming client connections

Running the Client

python mbylut003_client.py

	•	Enter the server IP address and port
	•	Provide a nickname when prompted
	•	Start sending messages once connected

Run multiple client instances to simulate concurrent users.

⸻

Project Structure

├── server.py        # Multithreaded TCP server 
├── mbylut003_client.py        # TCP client implementation 
├── README.md
├── report.pdf       # Technical report and analysis

⸻

Learning Outcomes

This project demonstrates:
	•	Practical understanding of TCP/IP communication
	•	Concurrent programming using threads
	•	Client–server architecture design
	•	Debugging networked systems
	•	Collaborative development with clear component ownership
	•	Translating technical implementation into structured documentation

⸻

Notes
	•	This project prioritizes conceptual correctness and clarity over production-grade security.
	•	Authentication, encryption, and fault tolerance are intentionally out of scope.
	•	The implementation is suitable for educational and portfolio purposes.

Author Contributions
	•	Server: Group-developed as part of a networking coursework project
	•	Client & Documentation: Independently implemented and authored


