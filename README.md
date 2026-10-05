# NetworkComm 
TCP Client–Server Chat Application

# Overview
This repository contains a Python-based TCP client–server chat application designed to demonstrate core networking, concurrency, and protocol-design concepts. 
The system enables multiple clients to connect to a central server and exchange messages in real time using socket programming and multithreading.

The server component was originally developed collaboratively as part of a group project, focusing on connection handling, concurrency control, and message routing.
Additional enhancements to the server were independently implemented, including structured message logging, improved error handling, clearer message formatting, and more robust coordination between clients.

The client component was independently implemented, handling user interaction, server communication, connection retry logic, and asynchronous message reception.

The project prioritises correctness, security and clear protocol design over UI complexity.

## Key Features
TCP socket–based communication, secured with TLS
• Authenticated users (salted scrypt), lockout, rate limiting and input validation
• Length-prefixed JSON framing
• Multithreaded server supporting multiple concurrent clients
Server-side enhancements:
• Structured logging of connections, disconnections, and message events
• Improved error handling for unexpected client disconnects
• Clear, timestamped message formatting
• Asynchronous message handling on the client side
• Explicit, documented wire protocol (see protocol.py)
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

Prerequisites: Python 3.10+ and OpenSSL (to generate a test certificate). No third-party packages.

```
./gen_cert.sh                      # one-off: creates certs/server.crt and certs/server.key
python server3.py                  # listens on 127.0.0.1:44444 over TLS
python mbylut003_client.py         # --host, --port and --cafile are optional
python -m unittest -v              # 28 end-to-end tests
```

On first connection choose **register**, then log in on later runs. Run several clients to simulate users.
Accounts are stored (salted scrypt hashes only) in `users.json`.

# Security design

See [THREAT_MODEL.md](THREAT_MODEL.md) for the full table mapping each threat to its mitigation and test.

- **TLS 1.2+** for all traffic; the client verifies certificate and hostname.
- **Authentication** with salted scrypt hashes, account lockout and constant-time comparison.
- **Length-prefixed JSON framing** with a 16 KiB cap, replacing the old implicit one-`recv`-one-message assumption.
- **Input validation** on every field, including rejection of control characters.
- **Authorisation**: only room members can post; the sender identity is always the authenticated user.
- **Abuse controls**: per-connection token-bucket rate limiting, connection cap and timeouts.

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
	•	Built to study protocol and security design; it has not been independently audited.

## Limitations
	•	No end-to-end encryption: the server can read all messages.
	•	Only accounts persist; rooms, sessions and rate-limit state are in memory.
	•	Rate limiting and lockout are per connection / per account, not per IP.
	•	Thread-per-connection design; single server; terminal client.
	•	Self-signed certificate for local use.

## Future Enhancements
	•	End-to-end encryption between clients, persistent chat history, per-IP throttling,
	  an asyncio server, and certificate rotation tooling.
