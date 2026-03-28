#!/usr/bin/env python3
"""earthproxy — SOCKS5-to-Reticulum Proxy Daemon

Listens as a SOCKS5 proxy on localhost. Accepts CONNECT requests for .ret
addresses, establishes Reticulum links, and proxies HTTP traffic between
the browser and the Reticulum destination.
"""

import os
import sys
import socket
import struct
import threading
import time
import json
import configparser
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import RNS

# Must match earthserv's app name and aspects
SERVER_APP_NAME = "earthserv"
SERVER_ASPECTS = ["http"]

# SOCKS5 constants
SOCKS_VERSION = 0x05
SOCKS_AUTH_NONE = 0x00
SOCKS_AUTH_USERPASS = 0x02
SOCKS_CMD_CONNECT = 0x01
SOCKS_ATYPE_DOMAIN = 0x03
SOCKS_REPLY_SUCCESS = 0x00
SOCKS_REPLY_GENERAL_FAILURE = 0x01
SOCKS_REPLY_NOT_ALLOWED = 0x02
SOCKS_REPLY_NETWORK_UNREACHABLE = 0x03
SOCKS_REPLY_HOST_UNREACHABLE = 0x04
SOCKS_REPLY_COMMAND_NOT_SUPPORTED = 0x07
SOCKS_REPLY_ADDRESS_TYPE_NOT_SUPPORTED = 0x08

WELCOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Earth Browser</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f5f5f0;color:#1a1f36;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,sans-serif;font-size:15px;line-height:1.7;display:flex;align-items:center;justify-content:center;min-height:100vh}
.page{max-width:480px;padding:40px 24px;text-align:center}
h1{font-size:28px;color:#1a1f36;margin-bottom:6px;letter-spacing:0.02em;font-weight:700}
.tag{color:#4a9a5a;font-size:14px;margin-bottom:36px}
.url-box{background:#fff;border:1px solid #e0e0d8;border-radius:12px;padding:14px 20px;margin-bottom:28px;display:flex;align-items:center;justify-content:center;gap:6px;box-shadow:0 1px 3px rgba(0,0,0,0.04)}
.url-prefix{color:#9a9a90;font-family:monospace;font-size:13px}
.url-hash{color:#2a7a3a;font-family:monospace;font-size:13px}
.info{font-size:13px;color:#6a6a64;line-height:1.8;margin-bottom:24px}
.info strong{color:#1a1f36}
.cards{display:flex;gap:12px;margin-bottom:24px;text-align:left}
.card{flex:1;background:#fff;border:1px solid #e0e0d8;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.04)}
.card h3{font-size:11px;color:#4a9a5a;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.06em;font-weight:700}
.card p{font-size:12px;color:#6a6a64;margin:0;line-height:1.5}
.foot{font-size:11px;color:#c0c0b8;margin-top:20px}
</style>
</head>
<body>
<div class="page">
<img src="http://_earth.ret/logo" alt="" style="width:80px;height:80px;margin-bottom:16px;">
<h1>Earth Browser</h1>
<p class="tag">Browsing over Reticulum</p>

<div class="url-box">
<span class="url-prefix">http://</span>
<span class="url-hash">&lt;destination_hash&gt;</span>
<span class="url-prefix">.ret</span>
</div>

<div class="info">
<p>Enter a <strong>.ret</strong> address to browse over the Reticulum network.</p>
<p>Regular websites work too. All <strong>.ret</strong> traffic is end-to-end encrypted.</p>
<p>Click the <strong>shield icon</strong> to manage identity, privacy mode, and JavaScript.</p>
</div>

<div class="cards">
<div class="card">
<h3>Encrypted</h3>
<p>X25519 + AES-256 on every link. No TLS needed.</p>
</div>
<div class="card">
<h3>Anonymous</h3>
<p>No source addresses. Servers can't see who you are.</p>
</div>
<div class="card">
<h3>Sovereign</h3>
<p>Addresses are keypairs you generate. No DNS, no CAs.</p>
</div>
</div>

<p class="foot">Earth Network (ERTH)</p>
</div>
</body>
</html>"""


class ControlHandler(BaseHTTPRequestHandler):
    """HTTP handler for the earthproxy control API (localhost only)."""

    def log_message(self, format, *args):
        RNS.log(f"[Control] {format % args}", RNS.LOG_DEBUG)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        proxy = self.server.proxy

        if self.path == "/status":
            # Get current identity hash based on privacy mode
            identity_hash = ""
            if hasattr(proxy, "session_identity"):
                identity_hash = proxy.session_identity.hexhash
            dest_identities = {
                h: proxy.destination_identities[h].hexhash
                for h in proxy.destination_identities
            } if proxy.privacy_mode == "ephemeral_destination" else {}

            self._send_json({
                "running": True,
                "privacy_mode": proxy.privacy_mode,
                "identity_hash": identity_hash,
                "identity_public_key": proxy.session_identity.get_public_key().hex() if hasattr(proxy, "session_identity") else "",
                "destination_identities": dest_identities,
                "pinned_fallback": proxy.pinned_fallback,
                "pinned_destinations": list(proxy._loaded_pinned.keys()),
                "active_connections": proxy.active_connections,
                "total_requests": proxy.total_requests,
                "reticulum": True,
            })

        elif self.path == "/pinned":
            self._send_json({
                "pinned": {h: True for h in proxy._loaded_pinned.keys()},
            })

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        proxy = self.server.proxy

        if self.path == "/privacy-mode":
            data = self._read_json()
            mode = data.get("mode")
            if mode not in ("ephemeral_session", "ephemeral_destination", "pinned"):
                self._send_json({"error": "invalid mode"}, 400)
                return

            old_mode = proxy.privacy_mode
            if mode != old_mode:
                proxy.privacy_mode = mode
                # Only regenerate identity when actually switching modes
                if mode in ("ephemeral_session", "pinned"):
                    proxy.session_identity = RNS.Identity()
                if mode == "ephemeral_destination":
                    proxy.destination_identities = {}

            RNS.log(f"Privacy mode changed: {old_mode} -> {mode}")
            self._send_json({"ok": True, "mode": mode})

        elif self.path == "/new-identity":
            old_hash = proxy.session_identity.hexhash if hasattr(proxy, "session_identity") else ""
            proxy.session_identity = RNS.Identity()
            proxy.destination_identities = {}
            new_hash = proxy.session_identity.hexhash
            RNS.log(f"New identity generated: {old_hash} -> {new_hash}")
            self._send_json({
                "ok": True,
                "identity_hash": new_hash,
                "old_hash": old_hash,
            })

        elif self.path == "/pin-identity":
            data = self._read_json()
            dest_hash = data.get("dest_hash", "").lower()
            if not dest_hash or len(dest_hash) != 32:
                self._send_json({"error": "invalid dest_hash"}, 400)
                return

            # Create and store a new pinned identity
            ident = RNS.Identity()
            id_dir = os.path.expanduser("~/.earthbrowser/identities")
            os.makedirs(id_dir, exist_ok=True)
            id_path = os.path.join(id_dir, f"{dest_hash}.id")
            ident.to_file(id_path)
            proxy._loaded_pinned[dest_hash] = ident
            RNS.log(f"Pinned new identity for {dest_hash}")
            self._send_json({"ok": True, "dest_hash": dest_hash})

        else:
            self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        proxy = self.server.proxy

        if self.path.startswith("/pin-identity/"):
            dest_hash = self.path[len("/pin-identity/"):].lower()
            if dest_hash in proxy._loaded_pinned:
                del proxy._loaded_pinned[dest_hash]
                # Remove identity file
                id_path = os.path.expanduser(f"~/.earthbrowser/identities/{dest_hash}.id")
                if os.path.exists(id_path):
                    os.remove(id_path)
                RNS.log(f"Unpinned identity for {dest_hash}")
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "not pinned"}, 404)
        else:
            self._send_json({"error": "not found"}, 404)


class EarthProxy:
    def __init__(self, listen_addr="127.0.0.1", listen_port=9150,
                 control_port=9151, privacy_mode="ephemeral_session",
                 pinned_identities=None, pinned_fallback="ephemeral_session",
                 config_path=None):
        self.listen_addr = listen_addr
        self.listen_port = listen_port
        self.control_port = control_port
        self.privacy_mode = privacy_mode
        self.pinned_fallback = pinned_fallback
        self.pinned_identities = pinned_identities or {}
        self.active_connections = 0
        self.total_requests = 0
        self.js_level = 0              # 0=disabled, 1=per-destination, 2=global
        self.js_whitelist = set()      # destination hashes where JS is allowed

        # Initialize Reticulum
        self.reticulum = RNS.Reticulum(configdir=config_path)

        # Identity management
        if privacy_mode in ("ephemeral_session", "pinned"):
            self.session_identity = RNS.Identity()
        self.destination_identities = {}  # dest_hash_hex -> Identity (for per-destination mode)

        # Load pinned identities from files
        self._loaded_pinned = {}
        for dest_hex, id_path in self.pinned_identities.items():
            id_path = os.path.expanduser(id_path)
            if os.path.exists(id_path):
                self._loaded_pinned[dest_hex] = RNS.Identity.from_file(id_path)
                RNS.log(f"Loaded pinned identity for {dest_hex}")
            else:
                ident = RNS.Identity()
                os.makedirs(os.path.dirname(id_path), exist_ok=True)
                ident.to_file(id_path)
                self._loaded_pinned[dest_hex] = ident
                RNS.log(f"Created pinned identity for {dest_hex}, saved to {id_path}")

        # SOCKS5 server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.listen_addr, self.listen_port))
        self.server_socket.listen(16)

        # Control API server
        self.control_server = HTTPServer((self.listen_addr, self.control_port), ControlHandler)
        self.control_server.proxy = self

        RNS.log(f"earthproxy listening on {self.listen_addr}:{self.listen_port}")
        RNS.log(f"Control API on {self.listen_addr}:{self.control_port}")
        RNS.log(f"Privacy mode: {self.privacy_mode}")

    def get_identity_for_destination(self, dest_hash_hex):
        """Return the appropriate local identity based on privacy mode."""
        if self.privacy_mode == "pinned" and dest_hash_hex in self._loaded_pinned:
            return self._loaded_pinned[dest_hash_hex]

        effective_mode = self.privacy_mode
        if self.privacy_mode == "pinned":
            effective_mode = self.pinned_fallback

        if effective_mode == "ephemeral_destination":
            if dest_hash_hex not in self.destination_identities:
                self.destination_identities[dest_hash_hex] = RNS.Identity()
            return self.destination_identities[dest_hash_hex]
        else:
            return self.session_identity

    def run(self):
        """Main accept loop."""
        # Start control API in background
        control_thread = threading.Thread(
            target=self.control_server.serve_forever,
            daemon=True
        )
        control_thread.start()

        try:
            while True:
                client_sock, addr = self.server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_sock,),
                    daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            RNS.log("earthproxy shutting down")
            self.control_server.shutdown()
            self.server_socket.close()

    def socks5_reply(self, sock, reply_code):
        """Send a SOCKS5 reply."""
        sock.sendall(bytes([
            SOCKS_VERSION, reply_code, 0x00,
            0x01,          # address type: IPv4
            0, 0, 0, 0,   # bind address
            0, 0           # bind port
        ]))

    def handle_client(self, client_sock):
        """Handle a single SOCKS5 client connection."""
        self.active_connections += 1
        self.total_requests += 1
        link = None
        try:
            # --- SOCKS5 Handshake ---

            # Step 1: Version and auth method negotiation
            data = client_sock.recv(256)
            if len(data) < 3 or data[0] != SOCKS_VERSION:
                client_sock.close()
                return

            num_methods = data[1]
            methods = data[2:2 + num_methods]

            if SOCKS_AUTH_USERPASS in methods:
                # Accept username/password auth (Tor Browser uses this for
                # circuit isolation — we accept any credentials)
                client_sock.sendall(bytes([SOCKS_VERSION, SOCKS_AUTH_USERPASS]))
                # Read username/password subnegotiation
                auth_data = client_sock.recv(512)
                if len(auth_data) < 2 or auth_data[0] != 0x01:
                    client_sock.close()
                    return
                # Reply: auth success
                client_sock.sendall(bytes([0x01, 0x00]))
            elif SOCKS_AUTH_NONE in methods:
                # Accept no-auth
                client_sock.sendall(bytes([SOCKS_VERSION, SOCKS_AUTH_NONE]))
            else:
                # No acceptable auth method
                client_sock.sendall(bytes([SOCKS_VERSION, 0xFF]))
                client_sock.close()
                return

            # Step 2: Connection request
            data = client_sock.recv(512)
            if len(data) < 7 or data[0] != SOCKS_VERSION:
                client_sock.close()
                return

            cmd = data[1]
            if cmd != SOCKS_CMD_CONNECT:
                self.socks5_reply(client_sock, SOCKS_REPLY_COMMAND_NOT_SUPPORTED)
                client_sock.close()
                return

            atype = data[3]
            if atype != SOCKS_ATYPE_DOMAIN:
                self.socks5_reply(client_sock, SOCKS_REPLY_ADDRESS_TYPE_NOT_SUPPORTED)
                client_sock.close()
                return

            # Parse domain name
            domain_len = data[4]
            domain = data[5:5 + domain_len].decode("utf-8")
            port = struct.unpack("!H", data[5 + domain_len:7 + domain_len])[0]

            # Route .ret addresses through Reticulum, everything else through clearnet
            if not domain.endswith(".ret"):
                self.handle_clearnet(client_sock, domain, port)
                return

            dest_hash_hex = domain[:-4]  # Strip .ret suffix

            # Handle internal control address: _earth.ret
            if dest_hash_hex == "_earth":
                self.socks5_reply(client_sock, SOCKS_REPLY_SUCCESS)
                self.handle_control_request(client_sock)
                return

            # Reject HTTPS (443) for .ret — Reticulum encrypts, no TLS needed
            # Browser falls back to HTTP (80) automatically
            if port == 443:
                self.socks5_reply(client_sock, SOCKS_REPLY_SUCCESS)
                client_sock.close()
                return

            RNS.log(f"CONNECT to {dest_hash_hex}.ret:{port}")

            # Validate hex hash (should be 32 hex chars = 16 bytes)
            try:
                dest_hash = bytes.fromhex(dest_hash_hex)
                if len(dest_hash) != 16:
                    raise ValueError("Invalid hash length")
            except ValueError:
                RNS.log(f"Invalid destination hash: {dest_hash_hex}", RNS.LOG_ERROR)
                self.socks5_reply(client_sock, SOCKS_REPLY_HOST_UNREACHABLE)
                client_sock.close()
                return

            # --- Resolve Destination ---

            server_identity = RNS.Identity.recall(dest_hash)
            has_path = RNS.Transport.has_path(dest_hash)

            if server_identity is None or not has_path:
                RNS.log(f"Requesting path to {dest_hash_hex}...")
                RNS.Transport.request_path(dest_hash)

                start = time.time()
                timeout = 15
                while time.time() - start < timeout:
                    server_identity = RNS.Identity.recall(dest_hash)
                    has_path = RNS.Transport.has_path(dest_hash)
                    if server_identity is not None and has_path:
                        break
                    time.sleep(0.1)

                if server_identity is None:
                    RNS.log(f"Could not resolve identity for {dest_hash_hex}", RNS.LOG_ERROR)
                    self.socks5_reply(client_sock, SOCKS_REPLY_HOST_UNREACHABLE)
                    client_sock.close()
                    return

            # Create outgoing destination
            server_destination = RNS.Destination(
                server_identity,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                SERVER_APP_NAME,
                *SERVER_ASPECTS
            )

            # Verify hash matches
            if server_destination.hash != dest_hash:
                RNS.log(
                    f"Destination hash mismatch: expected {dest_hash_hex}, "
                    f"got {server_destination.hexhash}",
                    RNS.LOG_ERROR
                )
                self.socks5_reply(client_sock, SOCKS_REPLY_HOST_UNREACHABLE)
                client_sock.close()
                return

            # --- Establish Reticulum Link ---

            link_ready = threading.Event()
            link_failed = threading.Event()

            def on_established(lnk):
                link_ready.set()

            def on_closed(lnk):
                if not link_ready.is_set():
                    link_failed.set()

            link = RNS.Link(server_destination, established_callback=on_established)
            link.set_link_closed_callback(on_closed)

            # Wait for link establishment
            link_timeout = 30
            start = time.time()
            while not link_ready.is_set() and not link_failed.is_set():
                if time.time() - start > link_timeout:
                    break
                time.sleep(0.1)

            if not link_ready.is_set():
                RNS.log(f"Link establishment failed to {dest_hash_hex}", RNS.LOG_ERROR)
                self.socks5_reply(client_sock, SOCKS_REPLY_HOST_UNREACHABLE)
                client_sock.close()
                if link:
                    link.teardown()
                return

            RNS.log(f"Link established to {dest_hash_hex}")

            # Identify if using pinned mode for this destination
            if self.privacy_mode == "pinned" and dest_hash_hex in self._loaded_pinned:
                link.identify(self._loaded_pinned[dest_hash_hex])

            # SOCKS5 success - connection established
            self.socks5_reply(client_sock, SOCKS_REPLY_SUCCESS)

            # --- Proxy HTTP Traffic ---

            # Read HTTP request from browser
            http_request = self.read_http_request(client_sock)
            if not http_request:
                RNS.log("Browser closed connection before sending request", RNS.LOG_DEBUG)
                link.teardown()
                client_sock.close()
                return

            RNS.log(f"Proxying {len(http_request)} byte request to {dest_hash_hex}")

            # Send request over Reticulum link and wait for response
            response_event = threading.Event()
            response_data = [None]

            def on_response(receipt):
                response_data[0] = receipt.get_response()
                response_event.set()

            def on_request_failed(receipt):
                RNS.log(f"Request failed to {dest_hash_hex}", RNS.LOG_ERROR)
                response_event.set()

            link.request(
                "/http",
                http_request,
                response_callback=on_response,
                failed_callback=on_request_failed,
                timeout=60
            )

            # Wait for response
            response_event.wait(timeout=60)

            if response_data[0] is not None:
                response = self.inject_csp(response_data[0], dest_hash_hex)
                RNS.log(f"Relaying {len(response)} byte response to browser")
                client_sock.sendall(response)
            else:
                # Send a gateway timeout response
                timeout_response = (
                    b"HTTP/1.1 504 Gateway Timeout\r\n"
                    b"Content-Type: text/html\r\n"
                    b"Connection: close\r\n\r\n"
                    b"<html><body><h1>504 Gateway Timeout</h1>"
                    b"<p>The Reticulum destination did not respond.</p>"
                    b"</body></html>"
                )
                client_sock.sendall(timeout_response)

            # Cleanup
            link.teardown()
            client_sock.close()

        except Exception as e:
            RNS.log(f"Error handling client: {e}", RNS.LOG_ERROR)
            try:
                if link:
                    link.teardown()
            except:
                pass
            try:
                client_sock.close()
            except:
                pass
        finally:
            self.active_connections -= 1

    def handle_clearnet(self, client_sock, domain, port):
        """Proxy non-.ret traffic directly to the internet via TCP."""
        try:
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote.settimeout(15)
            remote.connect((domain, port))
            self.socks5_reply(client_sock, SOCKS_REPLY_SUCCESS)

            # Bidirectional relay
            import select
            client_sock.setblocking(False)
            remote.setblocking(False)
            sockets = [client_sock, remote]

            while True:
                readable, _, errored = select.select(sockets, [], sockets, 30)
                if errored:
                    break
                if not readable:
                    break  # timeout
                for s in readable:
                    data = s.recv(65536)
                    if not data:
                        sockets = []  # trigger exit
                        break
                    if s is client_sock:
                        remote.sendall(data)
                    else:
                        client_sock.sendall(data)
                if not sockets:
                    break
        except (socket.error, OSError) as e:
            RNS.log(f"Clearnet proxy to {domain}:{port} failed: {e}", RNS.LOG_DEBUG)
            try:
                self.socks5_reply(client_sock, SOCKS_REPLY_HOST_UNREACHABLE)
            except:
                pass
        finally:
            try:
                remote.close()
            except:
                pass
            try:
                client_sock.close()
            except:
                pass

    def inject_csp(self, response, dest_hash_hex):
        """Inject Content-Security-Policy header based on JS security level."""
        js_allowed = (
            self.js_level == 2 or
            (self.js_level == 1 and dest_hash_hex in self.js_whitelist)
        )

        if js_allowed:
            csp = "worker-src 'none'; object-src 'none'"
        else:
            csp = "script-src 'none'; worker-src 'none'; object-src 'none'"

        # Find end of first line (status line) and inject after it
        header_end = response.find(b"\r\n\r\n")
        if header_end == -1:
            return response

        headers = response[:header_end]
        body = response[header_end:]
        csp_header = f"\r\nContent-Security-Policy: {csp}".encode()
        return headers + csp_header + body

    def handle_control_request(self, client_sock):
        """Handle HTTP requests to the internal _earth.ret control address."""
        try:
            http_request = self.read_http_request(client_sock)
            if not http_request:
                client_sock.close()
                return

            request_text = http_request.decode("utf-8", errors="replace")
            lines = request_text.split("\r\n")
            parts = lines[0].split(" ", 2)
            method, path = parts[0], parts[1] if len(parts) > 1 else "/"

            # Build JSON response based on path
            if path == "/status" or path == "/":
                identity_hash = ""
                pub_key = ""
                if hasattr(self, "session_identity"):
                    identity_hash = self.session_identity.hexhash
                    pub_key = self.session_identity.get_public_key().hex()
                body = json.dumps({
                    "running": True,
                    "privacy_mode": self.privacy_mode,
                    "identity_hash": identity_hash,
                    "identity_public_key": pub_key,
                    "pinned_destinations": list(self._loaded_pinned.keys()),
                    "active_connections": self.active_connections,
                    "total_requests": self.total_requests,
                    "js_level": self.js_level,
                    "js_whitelist": list(self.js_whitelist),
                }).encode()
            elif path == "/new-identity" and method == "POST":
                old_hash = self.session_identity.hexhash if hasattr(self, "session_identity") else ""
                self.session_identity = RNS.Identity()
                self.destination_identities = {}
                new_hash = self.session_identity.hexhash
                RNS.log(f"New identity: {old_hash} -> {new_hash}")
                body = json.dumps({
                    "ok": True,
                    "identity_hash": new_hash,
                    "old_hash": old_hash,
                }).encode()
            elif path.startswith("/privacy-mode") and method == "POST":
                content_start = request_text.find("\r\n\r\n") + 4
                req_body = request_text[content_start:]
                data = json.loads(req_body) if req_body.strip() else {}
                mode = data.get("mode", "")
                if mode in ("ephemeral_session", "ephemeral_destination", "pinned"):
                    self.privacy_mode = mode
                    if mode in ("ephemeral_session", "pinned"):
                        self.session_identity = RNS.Identity()
                    if mode == "ephemeral_destination":
                        self.destination_identities = {}
                    body = json.dumps({"ok": True, "mode": mode}).encode()
                else:
                    body = json.dumps({"error": "invalid mode"}).encode()
            elif path == "/js-level" and method == "POST":
                content_start = request_text.find("\r\n\r\n") + 4
                req_body = request_text[content_start:]
                data = json.loads(req_body) if req_body.strip() else {}
                level = data.get("level")
                if level in (0, 1, 2):
                    self.js_level = level
                    RNS.log(f"JS security level set to {level}")
                    body = json.dumps({"ok": True, "js_level": level}).encode()
                else:
                    body = json.dumps({"error": "invalid level"}).encode()
            elif path == "/js-whitelist" and method == "POST":
                content_start = request_text.find("\r\n\r\n") + 4
                req_body = request_text[content_start:]
                data = json.loads(req_body) if req_body.strip() else {}
                action = data.get("action")
                dest = data.get("dest_hash", "").lower()
                if action == "add" and dest:
                    self.js_whitelist.add(dest)
                    body = json.dumps({"ok": True, "whitelist": list(self.js_whitelist)}).encode()
                elif action == "remove" and dest:
                    self.js_whitelist.discard(dest)
                    body = json.dumps({"ok": True, "whitelist": list(self.js_whitelist)}).encode()
                else:
                    body = json.dumps({"error": "invalid action"}).encode()
            elif path == "/logo":
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erth-browser.jpg")
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        body = f.read()
                else:
                    body = b""
                response = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode() + body
                client_sock.sendall(response)
                client_sock.close()
                return
            elif path == "/welcome":
                body = WELCOME_HTML.encode("utf-8")
                response = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode() + body
                client_sock.sendall(response)
                client_sock.close()
                return
            else:
                body = json.dumps({"error": "not found"}).encode()

            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Connection: close\r\n\r\n"
            ).encode() + body

            client_sock.sendall(response)
            client_sock.close()
        except Exception as e:
            RNS.log(f"Control request error: {e}", RNS.LOG_ERROR)
            try:
                client_sock.close()
            except:
                pass

    def read_http_request(self, sock):
        """Read a complete HTTP request from a TCP socket."""
        data = b""
        sock.settimeout(30)
        try:
            # Read until we have the complete headers
            while b"\r\n\r\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    return None
                data += chunk

            # Parse Content-Length if present
            header_end = data.index(b"\r\n\r\n") + 4
            headers_text = data[:header_end].decode("utf-8", errors="replace").lower()

            content_length = 0
            for line in headers_text.split("\r\n"):
                if line.startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
                    break

            # Read remaining body if needed
            body_received = len(data) - header_end
            while body_received < content_length:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                body_received += len(chunk)

        except socket.timeout:
            if data:
                return data
            return None
        finally:
            sock.settimeout(None)

        return data


def load_config():
    """Load configuration from ~/.earthbrowser/config if it exists."""
    config = configparser.ConfigParser()
    config_file = os.path.expanduser("~/.earthbrowser/config")

    settings = {
        "listen_addr": "127.0.0.1",
        "listen_port": 9152,
        "control_port": 9153,
        "privacy_mode": "ephemeral_session",
        "pinned_fallback": "ephemeral_session",
        "pinned_identities": {},
        "rns_config": None,
    }

    if os.path.exists(config_file):
        config.read(config_file)
        settings["listen_addr"] = config.get("proxy", "listen_address",
                                              fallback=settings["listen_addr"])
        settings["listen_port"] = config.getint("proxy", "listen_port",
                                                fallback=settings["listen_port"])
        settings["control_port"] = config.getint("proxy", "control_port",
                                                 fallback=settings["control_port"])
        settings["privacy_mode"] = config.get("privacy", "default_mode",
                                              fallback=settings["privacy_mode"])
        settings["pinned_fallback"] = config.get("privacy", "pinned_fallback",
                                                 fallback=settings["pinned_fallback"])
        if config.has_section("reticulum"):
            settings["rns_config"] = config.get("reticulum", "config_path",
                                                fallback=None)
        if config.has_section("pinned_identities"):
            for dest_hex, id_path in config.items("pinned_identities"):
                settings["pinned_identities"][dest_hex] = id_path

    return settings


def main():
    parser = argparse.ArgumentParser(
        description="earthproxy — SOCKS5-to-Reticulum Proxy Daemon"
    )
    parser.add_argument(
        "-a", "--address",
        help="Listen address (default: 127.0.0.1)",
        default=None
    )
    parser.add_argument(
        "-p", "--port",
        help="Listen port (default: 9150)",
        type=int,
        default=None
    )
    parser.add_argument(
        "-m", "--mode",
        help="Privacy mode: ephemeral_session, ephemeral_destination, pinned",
        default=None
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to Reticulum config directory",
        default=None
    )
    args = parser.parse_args()

    # Load config file, then override with CLI args
    settings = load_config()
    if args.address:
        settings["listen_addr"] = args.address
    if args.port:
        settings["listen_port"] = args.port
    if args.mode:
        settings["privacy_mode"] = args.mode
    if args.config:
        settings["rns_config"] = args.config

    proxy = EarthProxy(
        listen_addr=settings["listen_addr"],
        listen_port=settings["listen_port"],
        control_port=settings["control_port"],
        privacy_mode=settings["privacy_mode"],
        pinned_identities=settings["pinned_identities"],
        pinned_fallback=settings["pinned_fallback"],
        config_path=settings["rns_config"],
    )
    proxy.run()


if __name__ == "__main__":
    main()
