# Threat model

Scope: the chat server (`server3.py`), client (`mbylut003_client.py`), wire protocol (`protocol.py`)
and credential store (`auth.py`). Attacker capabilities considered: a network attacker who can read,
inject and modify traffic; an unauthenticated remote client; an authenticated but malicious user.

| # | Threat | Mitigation | Test |
|---|--------|------------|------|
| 1 | Eavesdropping / tampering on the wire | TLS 1.2+ for all traffic; the client verifies the certificate chain and hostname and has no option to disable verification | `TransportSecurityTests` |
| 2 | Man-in-the-middle with a rogue certificate | Client trusts only the configured certificate/CA | `test_untrusted_certificate_rejected`, `test_hostname_mismatch_rejected` |
| 3 | Downgrade to legacy TLS or plaintext | `minimum_version = TLSv1_2`; plaintext connections fail the handshake | `test_old_tls_versions_refused`, `test_plaintext_client_gets_nothing` |
| 4 | Impersonation | Identity is the authenticated username, set by the server; `from` fields sent by clients are ignored | `test_sender_name_comes_from_login_not_message` |
| 5 | Credential theft from the server | Per-user random salt, scrypt (n=2^14, r=8, p=1), never stored or logged in plaintext; store file mode 0600 | `AuthTests` |
| 6 | Online password guessing | Per-account lockout (5 failures -> 60 s), 5 attempts per connection, constant-time comparison, unknown users cost the same scrypt work as known ones | `test_lockout_after_repeated_failures` |
| 7 | Message boundary confusion / request smuggling | Length-prefixed JSON frames, strict parsing, 16 KiB cap | `FramingTests` |
| 8 | Memory exhaustion via huge frames | Frame cap enforced before reading the body | `test_oversized_frame_drops_connection` |
| 9 | Flooding / resource exhaustion | Token-bucket rate limit per connection, disconnect on sustained abuse, global connection cap, handshake/auth/idle timeouts | `test_rate_limit`, `test_sustained_flooding_disconnects` |
| 10 | Terminal escape-sequence injection | Control characters rejected in all user text | `test_control_characters_refused` |
| 11 | Unauthorised room access | Only members can post; room names validated | `test_room_post_requires_membership`, `test_bad_room_name_refused` |
| 12 | Information leak via "hide" | Hidden users answer DMs exactly like nonexistent users | `test_hidden_user_indistinguishable_from_absent` |
| 13 | Crashes from malformed input | Type checks on every field; server stays up after malformed commands | `test_malformed_types_do_not_crash_server` |
| 14 | Corrupted frames from concurrent writers | Per-session send lock | (design) |

## Known gaps (out of scope / future work)
- **No end-to-end encryption**: the server sees all message content.
- **Rate limit and lockout are in-memory and per-connection/per-account**, not per-IP: an attacker can lock out a victim's account (a deliberate availability-for-integrity trade-off), and a restart clears state.
- **Thread-per-connection** does not scale to very large numbers of clients.
- **No password reset, account deletion or certificate rotation tooling.**
- **Self-signed certificate** for local use; a real deployment would use a CA-issued certificate.
- **No message persistence or audit log integrity protection.**
