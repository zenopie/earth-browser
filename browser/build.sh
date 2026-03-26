#!/bin/bash
# Earth Browser — Build / Conversion Script
#
# Takes a Tor Browser installation and converts it to Earth Browser:
#   1. Strips Tor-specific components (tor binary, tor launcher)
#   2. Installs Earth Browser extension
#   3. Applies preference overrides
#   4. Bundles earthproxy + Reticulum
#   5. Creates launcher script
#
# Usage:
#   ./build.sh /path/to/tor-browser /path/to/output
#
# Prerequisites:
#   - A Tor Browser installation (download from torproject.org)
#   - Python 3.10+ with pip
#   - This repository

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

if [ $# -lt 2 ]; then
    echo "Usage: $0 <tor-browser-dir> <output-dir>"
    echo ""
    echo "  tor-browser-dir: Path to extracted Tor Browser directory"
    echo "  output-dir:      Where to create Earth Browser"
    exit 1
fi

TOR_DIR="$(cd "$1" && pwd)"
OUT_DIR="$2"

# ---------------------------------------------------------------------------
# Detect platform and browser layout
# ---------------------------------------------------------------------------

if [ -d "$TOR_DIR/Browser" ]; then
    # Linux layout: TorBrowser/Browser/
    BROWSER_DIR="$TOR_DIR/Browser"
    PROFILE_DIR="$BROWSER_DIR/TorBrowser/Data/Browser/profile.default"
    DEFAULTS_DIR="$BROWSER_DIR/TorBrowser/Data/Browser"
    PREFS_DIR="$BROWSER_DIR/defaults/pref"
    EXTENSIONS_DIR="$PROFILE_DIR/extensions"
    PLATFORM="linux"
elif [ -d "$TOR_DIR/Contents/MacOS" ]; then
    # macOS layout: Tor Browser.app/Contents/MacOS/
    BROWSER_DIR="$TOR_DIR/Contents/MacOS"
    PROFILE_DIR="$TOR_DIR/Contents/Resources/TorBrowser/Data/Browser/profile.default"
    DEFAULTS_DIR="$TOR_DIR/Contents/Resources/TorBrowser/Data/Browser"
    PREFS_DIR="$BROWSER_DIR/defaults/pref"
    EXTENSIONS_DIR="$PROFILE_DIR/extensions"
    PLATFORM="macos"
else
    echo "Error: Could not detect Tor Browser layout in: $TOR_DIR"
    echo "Expected either Browser/ (Linux) or Contents/MacOS/ (macOS)"
    exit 1
fi

echo "=== Earth Browser Build ==="
echo "Source:   $TOR_DIR"
echo "Output:   $OUT_DIR"
echo "Platform: $PLATFORM"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Copy Tor Browser to output
# ---------------------------------------------------------------------------

echo "[1/6] Copying Tor Browser base..."
if [ -d "$OUT_DIR" ]; then
    echo "  Output directory exists. Remove it first or choose a different path."
    exit 1
fi

cp -a "$TOR_DIR" "$OUT_DIR"
echo "  Done."

# Update paths to point to output
if [ "$PLATFORM" = "linux" ]; then
    BROWSER_DIR="$OUT_DIR/Browser"
    PROFILE_DIR="$BROWSER_DIR/TorBrowser/Data/Browser/profile.default"
    DEFAULTS_DIR="$BROWSER_DIR/TorBrowser/Data/Browser"
    PREFS_DIR="$BROWSER_DIR/defaults/pref"
    EXTENSIONS_DIR="$PROFILE_DIR/extensions"
elif [ "$PLATFORM" = "macos" ]; then
    BROWSER_DIR="$OUT_DIR/Contents/MacOS"
    PROFILE_DIR="$OUT_DIR/Contents/Resources/TorBrowser/Data/Browser/profile.default"
    DEFAULTS_DIR="$OUT_DIR/Contents/Resources/TorBrowser/Data/Browser"
    PREFS_DIR="$BROWSER_DIR/defaults/pref"
    EXTENSIONS_DIR="$PROFILE_DIR/extensions"
fi

# ---------------------------------------------------------------------------
# Step 2: Remove Tor-specific components
# ---------------------------------------------------------------------------

echo "[2/6] Removing Tor components..."

# Remove tor binary and related files
for f in tor tor.real obfs4proxy snowflake-client meek-client lyrebird pt_config.json; do
    target="$BROWSER_DIR/TorBrowser/Tor/$f"
    [ -f "$target" ] && rm -f "$target" && echo "  Removed $f"
    # macOS paths
    target="$OUT_DIR/Contents/MacOS/Tor/$f"
    [ -f "$target" ] && rm -f "$target" && echo "  Removed $f (macOS)"
done

# Remove Tor launcher extension if present
for ext_dir in "$EXTENSIONS_DIR" "$BROWSER_DIR/browser/extensions"; do
    if [ -d "$ext_dir" ]; then
        for item in "$ext_dir"/tor-launcher* "$ext_dir"/*tor-launcher*; do
            [ -e "$item" ] && rm -rf "$item" && echo "  Removed $(basename "$item")"
        done
    fi
done

# Remove Tor-specific preference files
for f in "$PREFS_DIR"/tor-*.js "$PREFS_DIR"/*torbutton*.js; do
    [ -f "$f" ] && rm -f "$f" && echo "  Removed $(basename "$f")"
done

echo "  Done."

# ---------------------------------------------------------------------------
# Step 3: Install Earth Browser extension
# ---------------------------------------------------------------------------

echo "[3/6] Installing Earth Browser extension..."

EXTENSION_DEST="$EXTENSIONS_DIR/earth-browser@earthnetwork.ret.xpi"
mkdir -p "$EXTENSIONS_DIR"

# Package the extension as an XPI (ZIP)
(cd "$REPO_DIR/browser/extension" && zip -r -q "$EXTENSION_DEST" .)
echo "  Installed extension to $EXTENSION_DEST"

# ---------------------------------------------------------------------------
# Step 4: Apply preference overrides
# ---------------------------------------------------------------------------

echo "[4/6] Applying preference overrides..."

mkdir -p "$PREFS_DIR"
cp "$REPO_DIR/browser/preferences/earth-browser.js" "$PREFS_DIR/"
echo "  Installed earth-browser.js preferences"

# Also write to the profile's user.js for guaranteed application
mkdir -p "$PROFILE_DIR"
{
    echo "// Earth Browser — User Preferences (auto-generated)"
    echo "// These override any defaults set elsewhere."
    echo ""
    # Convert pref() to user_pref() for user.js
    sed 's/^pref(/user_pref(/' "$REPO_DIR/browser/preferences/earth-browser.js" | grep "^user_pref("
} > "$PROFILE_DIR/user.js"
echo "  Installed user.js to profile"

# ---------------------------------------------------------------------------
# Step 5: Bundle earthproxy + Reticulum
# ---------------------------------------------------------------------------

echo "[5/6] Bundling earthproxy..."

EARTH_DIR="$BROWSER_DIR/EarthBrowser"
mkdir -p "$EARTH_DIR"

cp "$REPO_DIR/earthproxy.py" "$EARTH_DIR/"
cp "$REPO_DIR/earthserv.py" "$EARTH_DIR/"
cp "$REPO_DIR/requirements.txt" "$EARTH_DIR/"

# Create a default config
mkdir -p "$EARTH_DIR/config"
cat > "$EARTH_DIR/config/earthbrowser.conf" << 'CONF'
[proxy]
listen_address = 127.0.0.1
listen_port = 9150

[privacy]
default_mode = ephemeral_session
pinned_fallback = ephemeral_session

[javascript]
js_level = 0
CONF

echo "  Bundled earthproxy, earthserv, and default config"

# ---------------------------------------------------------------------------
# Step 6: Create launcher script
# ---------------------------------------------------------------------------

echo "[6/6] Creating launcher..."

if [ "$PLATFORM" = "linux" ]; then
    FIREFOX_BIN="$BROWSER_DIR/firefox"

    cat > "$OUT_DIR/earth-browser" << 'LAUNCHER'
#!/bin/bash
# Earth Browser Launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BROWSER_DIR="$SCRIPT_DIR/Browser"
EARTH_DIR="$BROWSER_DIR/EarthBrowser"
PROXY_PID=""

cleanup() {
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        kill "$PROXY_PID" 2>/dev/null
        wait "$PROXY_PID" 2>/dev/null
    fi
}
trap cleanup EXIT

# Start earthproxy
echo "Starting earthproxy..."
python3 "$EARTH_DIR/earthproxy.py" &
PROXY_PID=$!

# Wait for proxy to be ready
for i in $(seq 1 30); do
    if python3 -c "
import socket
s = socket.socket()
s.settimeout(1)
try:
    s.connect(('127.0.0.1', 9150))
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

# Launch browser
echo "Starting Earth Browser..."
"$BROWSER_DIR/firefox" --profile "$BROWSER_DIR/TorBrowser/Data/Browser/profile.default" "$@"
LAUNCHER
    chmod +x "$OUT_DIR/earth-browser"
    echo "  Created launcher: $OUT_DIR/earth-browser"

elif [ "$PLATFORM" = "macos" ]; then
    cat > "$OUT_DIR/Contents/MacOS/earth-browser" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EARTH_DIR="$SCRIPT_DIR/EarthBrowser"
PROXY_PID=""

cleanup() {
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        kill "$PROXY_PID" 2>/dev/null
        wait "$PROXY_PID" 2>/dev/null
    fi
}
trap cleanup EXIT

echo "Starting earthproxy..."
python3 "$EARTH_DIR/earthproxy.py" &
PROXY_PID=$!

for i in $(seq 1 30); do
    if python3 -c "
import socket
s = socket.socket()
s.settimeout(1)
try:
    s.connect(('127.0.0.1', 9150))
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

echo "Starting Earth Browser..."
"$SCRIPT_DIR/firefox" "$@"
LAUNCHER
    chmod +x "$OUT_DIR/Contents/MacOS/earth-browser"
    echo "  Created launcher: Contents/MacOS/earth-browser"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

echo ""
echo "=== Build complete ==="
echo ""
echo "Earth Browser is ready at: $OUT_DIR"
if [ "$PLATFORM" = "linux" ]; then
    echo "Launch with: $OUT_DIR/earth-browser"
elif [ "$PLATFORM" = "macos" ]; then
    echo "Launch with: $OUT_DIR/Contents/MacOS/earth-browser"
fi
echo ""
echo "Note: Ensure Python 3.10+ and 'rns' are installed:"
echo "  pip install rns"
