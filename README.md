# Earth Browser

A Tor Browser fork that replaces the Tor onion routing network with the [Reticulum](https://reticulum.network/) cryptographic networking stack. The result is a privacy-hardened browser that renders HTML+CSS over Reticulum transport, with JavaScript disabled by default.

Part of the Earth Network (ERTH) ecosystem.

## How It Works

You browse to `.ret` addresses:

```
http://a4f2b8c91d3e7f06a4f2b8c91d3e7f06.ret/
```

Each address is a Reticulum destination hash — a cryptographic keypair. Traffic is end-to-end encrypted (X25519 + AES-256), with no TLS, no DNS, no IP addresses, and no certificate authorities.

Regular websites work too — clearnet traffic is proxied through normally.

## Architecture

```
Browser  →  earthproxy (SOCKS5)  →  Reticulum Link  →  earthserv
                                    (encrypted)
```

Three components:

- **earthproxy** — SOCKS5 proxy daemon on `localhost:9150`. Accepts browser connections, routes `.ret` addresses through encrypted Reticulum links, passes clearnet traffic through directly.
- **earthserv** — Reticulum HTTP server. Serves static HTML/CSS, handles POST forms and CGI scripts.
- **Browser** — Tor Browser with Tor removed and all anti-fingerprinting patches preserved. Shield icon controls Reticulum identity, privacy mode, and JavaScript security level.

## Privacy Features

### Reticulum Transport
- End-to-end encryption on every connection (X25519 ECDH + AES-256/ChaCha20)
- Initiator anonymity — servers cannot see your source address
- Self-sovereign addressing — destinations are locally generated keypairs
- Medium-agnostic — works over LoRa, packet radio, WiFi, TCP/IP, anything with >5bps

### Privacy Modes
- **Ephemeral Per-Session** (default) — fresh identity each session, destroyed on exit
- **Ephemeral Per-Destination** — separate identity for each destination, maximum unlinkability
- **Pinned Identity** — persistent identity for specific destinations (accounts, reputation)

### JavaScript Security Levels
- **Level 0: Disabled** (default) — no JavaScript execution, maximum privacy
- **Level 1: Per-Destination Whitelist** — JS only on explicitly allowed destinations, with warning dialog
- **Level 2: Global** — JS everywhere, with confirmation prompt warning about degraded privacy

### Always Blocked (regardless of JS level)
- WebRTC (IP leak prevention)
- Service Workers (persistent background execution)
- WebAssembly (native code execution)
- Geolocation, Bluetooth, USB, Serial, Notification, Push APIs
- Requests from `.ret` pages to non-Reticulum destinations
- All Tor Browser anti-fingerprinting patches remain active (canvas protection, letterboxing, font restriction, timing precision reduction)

## Quick Start

### Prerequisites
- Python 3.10+
- Reticulum: `pip install rns`
- [Tor Browser](https://www.torproject.org/download/) (as the base for packaging)

### Run Locally

Start a server:
```bash
python3 earthserv.py ./www -i identity.id -c /path/to/rns_config
```

Start the proxy:
```bash
python3 earthproxy.py -c /path/to/rns_config
```

Test with curl:
```bash
curl --socks5-hostname localhost:9150 http://<destination_hash>.ret/
```

### Package the Browser

```bash
./package.sh "/Applications/Tor Browser.app" ./EarthBrowser.app
```

This produces a self-contained app that:
1. Strips Tor from the Tor Browser
2. Patches all internal preferences and locked prefs
3. Replaces the shield panel with Reticulum identity/privacy/JS controls
4. Replaces "New Identity" with Reticulum keypair regeneration
5. Bundles earthproxy with a default Reticulum config
6. Creates a launcher that starts earthproxy automatically

Launch:
```bash
./EarthBrowser.app/Contents/MacOS/earth-browser
```

## Project Structure

```
earth-browser/
├── earthproxy.py          # SOCKS5→Reticulum proxy + clearnet passthrough
├── earthserv.py           # Reticulum HTTP server with POST/CGI
├── package.sh             # Builds distributable .app from Tor Browser
├── requirements.txt
├── browser/
│   ├── patches/           # omni.ja patches (shield panel, new identity, site identity)
│   └── preferences/       # Firefox preference overrides (~150 prefs)
└── www/                   # Demo site
    ├── index.html
    ├── about.html
    ├── forms.html         # Form interaction demo
    ├── jstest.html        # JavaScript security test page
    ├── style.css
    └── cgi-bin/
        ├── search.py      # Search form handler
        └── guestbook.py   # Guestbook with persistent storage
```

## Configuration

earthproxy reads `~/.earthbrowser/config`:

```ini
[proxy]
listen_address = 127.0.0.1
listen_port = 9150

[privacy]
default_mode = ephemeral_session

[javascript]
js_level = 0
```

## How Encryption Works

Reticulum's link encryption replaces TLS entirely:
- X25519 ECDH key exchange for every link
- AES-256 or ChaCha20 symmetric encryption
- Ed25519 signatures
- Forward secrecy via ephemeral keys
- Authentication of the destination (you know you're talking to the keypair that controls that hash)

No certificate authorities. No HTTPS. The browser connects via plain HTTP over an encrypted Reticulum link. The `http://` in the URL bar means "HTTP over Reticulum encryption" — not "unencrypted."

## References

- [Reticulum Network](https://reticulum.network/) — the underlying networking stack
- [Reticulum Manual](https://reticulum.network/manual/)
- [Reticulum Source](https://github.com/markqvist/Reticulum)
- [Tor Browser](https://www.torproject.org/) — the browser base

## License

Earth Browser source code is released into the public domain.

Reticulum is public domain (2016) by Mark Qvist.
Tor Browser is licensed under the Mozilla Public License.
