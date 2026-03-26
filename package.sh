#!/bin/bash
# Earth Browser — Package Script
#
# Assembles a distributable Earth Browser .app from a Tor Browser installation.
# Applies all patches, bundles earthproxy + Reticulum, and signs the result.
#
# Usage:
#   ./package.sh /path/to/TorBrowser.app /path/to/output/EarthBrowser.app
#
# Prerequisites:
#   - Tor Browser installation (download from torproject.org)
#   - Python 3.10+ with rns installed (pip install rns)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <TorBrowser.app> <output.app>"
    exit 1
fi

SRC="$1"
OUT="$2"

if [ -e "$OUT" ]; then
    echo "Error: $OUT already exists. Remove it first."
    exit 1
fi

echo "=== Earth Browser Packaging ==="
echo "Source: $SRC"
echo "Output: $OUT"
echo ""

# -------------------------------------------------------------------------
# Step 1: Copy base
# -------------------------------------------------------------------------
echo "[1/7] Copying Tor Browser..."
ditto "$SRC" "$OUT"

# Detect platform
if [ -d "$OUT/Contents/MacOS" ]; then
    PLATFORM="macos"
    BROWSER_DIR="$OUT/Contents/MacOS"
    RESOURCES="$OUT/Contents/Resources"
else
    PLATFORM="linux"
    BROWSER_DIR="$OUT/Browser"
    RESOURCES="$BROWSER_DIR"
fi

# -------------------------------------------------------------------------
# Step 2: Remove Tor binary
# -------------------------------------------------------------------------
echo "[2/7] Removing Tor daemon..."
rm -f "$BROWSER_DIR/Tor/tor" 2>/dev/null || true
rm -f "$OUT/Contents/MacOS/Tor/tor" 2>/dev/null || true

# -------------------------------------------------------------------------
# Step 2b: Replace app icon
# -------------------------------------------------------------------------
if [ -f "$SCRIPT_DIR/earth-browser.icns" ]; then
    echo "       Replacing app icon..."
    cp "$SCRIPT_DIR/earth-browser.icns" "$RESOURCES/firefox.icns"
    cp "$SCRIPT_DIR/earth-browser.icns" "$RESOURCES/document.icns"
fi

# Rebrand Info.plist
if [ "$PLATFORM" = "macos" ]; then
    sed -i '' 's/Tor Browser[^<]*/Earth Browser/g' "$OUT/Contents/Info.plist"
    sed -i '' 's/The Tor Project/Earth Network/g' "$OUT/Contents/Info.plist"
fi

# -------------------------------------------------------------------------
# Step 3: Patch browser/omni.ja
# -------------------------------------------------------------------------
echo "[3/7] Patching browser/omni.ja..."
OMNI_B="$RESOURCES/browser/omni.ja"
WORK_B="/tmp/earth_omni_browser"
rm -rf "$WORK_B" && mkdir -p "$WORK_B"

python3 -c "
import zipfile
with zipfile.ZipFile('$OMNI_B', 'r') as z:
    z.extractall('$WORK_B')
"

# Patch preferences
PREFS="$WORK_B/defaults/preferences/000-tor-browser.js"
sed -i '' 's/pref("extensions.torlauncher.start_tor", true);/pref("extensions.torlauncher.start_tor", false);/' "$PREFS"
sed -i '' 's/pref("extensions.torlauncher.prompt_at_startup", true);/pref("extensions.torlauncher.prompt_at_startup", false);/' "$PREFS"
sed -i '' 's/pref("torbrowser.settings.quickstart.enabled", false);/pref("torbrowser.settings.quickstart.enabled", true);/' "$PREFS"
sed -i '' 's/pref("dom.security.https_only_mode", true);/pref("dom.security.https_only_mode", false);/' "$PREFS"
sed -i '' 's/pref("dom.security.https_only_mode_pbm", true);/pref("dom.security.https_only_mode_pbm", false);/' "$PREFS"
echo 'pref("browser.fixup.domainsuffixwhitelist.ret", true);' >> "$PREFS"

# Lock HTTPS upgrade prefs off (Reticulum encrypts, no TLS needed)
echo 'pref("dom.security.https_first", false);' >> "$PREFS"
echo 'pref("dom.security.https_first_schemeless", false);' >> "$PREFS"
echo 'pref("browser.fixup.fallback-to-https", false);' >> "$PREFS"
echo 'pref("dom.security.https_only_mode", false);' >> "$PREFS"
echo 'pref("dom.security.https_only_mode_pbm", false);' >> "$PREFS"
sed -i '' 's/pref("network.proxy.allow_bypass", false, locked);/pref("network.proxy.allow_bypass", true);/' "$PREFS"
sed -i '' 's/pref("network.proxy.failover_direct", false, locked);/pref("network.proxy.failover_direct", true);/' "$PREFS"
sed -i '' 's/pref("extensions.installDistroAddons", false);/pref("extensions.installDistroAddons", true);/' "$PREFS"
sed -i '' 's/pref("xpinstall.signatures.required", true);/pref("xpinstall.signatures.required", false);/' "$PREFS"
sed -i '' 's/pref("extensions.enabledScopes", 5);/pref("extensions.enabledScopes", 15);/' "$PREFS"
echo 'pref("extensions.unifiedExtensions.enabled", false);' >> "$PREFS"

# Patch security level JS (replace with Earth Browser version)
cp "$SCRIPT_DIR/browser/patches/securityLevel.js" \
   "$WORK_B/chrome/browser/content/browser/securitylevel/securityLevel.js"

# Patch new identity JS
cp "$SCRIPT_DIR/browser/patches/newidentity.js" \
   "$WORK_B/chrome/browser/content/browser/newidentity.js"

# Patch site identity (treat .ret as secure like .onion)
cp "$SCRIPT_DIR/browser/patches/browser-siteIdentity.js" \
   "$WORK_B/chrome/browser/content/browser/browser-siteIdentity.js"

# Replace about:tor page with Earth Browser page
cp "$SCRIPT_DIR/browser/patches/aboutTor.html" \
   "$WORK_B/chrome/browser/content/browser/abouttor/aboutTor.html"

# Replace branding icons (tab icons, about page logo)
cp "$SCRIPT_DIR/browser/patches/branding/"*.png \
   "$WORK_B/chrome/browser/content/branding/"

# Fix homepage default from about:tor to about:blank
sed -i '' 's|pref("browser.startup.homepage", "about:tor");|pref("browser.startup.homepage", "about:blank");|' "$WORK_B/defaults/preferences/000-tor-browser.js"

# Disable auto-updates
sed -i '' 's|pref("app.update.auto", true);|pref("app.update.auto", false);|' "$WORK_B/defaults/preferences/000-tor-browser.js"
echo 'pref("app.update.enabled", false);' >> "$WORK_B/defaults/preferences/000-tor-browser.js"
echo 'pref("app.update.url", "");' >> "$WORK_B/defaults/preferences/000-tor-browser.js"

# Rebrand: replace "Tor Browser" with "Earth Browser" in all locale files
find "$WORK_B" -name "brand.properties" -exec sed -i '' 's/Tor Browser/Earth Browser/g;s/Tor Project/Earth Network/g' {} +
find "$WORK_B" -name "brand.ftl" -exec sed -i '' 's/Tor Browser/Earth Browser/g;s/Tor Project/Earth Network/g' {} +

# Fix default home page constant
sed -i '' 's|const kDefaultHomePage = "about:tor";|const kDefaultHomePage = "about:blank";|' "$WORK_B/modules/HomePage.sys.mjs"

# Patch security level panel in browser.xhtml
python3 - "$WORK_B/chrome/browser/content/browser/browser.xhtml" "$SCRIPT_DIR/browser/patches/securityLevel-panel.xhtml" << 'XHTML_PATCH'
import re, sys

xhtml_path, panel_path = sys.argv[1], sys.argv[2]

with open(xhtml_path, "r") as f:
    xhtml = f.read()

with open(panel_path, "r") as f:
    new_panel = f.read()

# Replace the panel
pattern = r'<panel id="securityLevel-panel".*?</panel>'
xhtml = re.sub(pattern, new_panel, xhtml, flags=re.DOTALL)

# Replace new-identity-button
xhtml = re.sub(
    r'<toolbarbutton id="new-identity-button".*?/>',
    '<toolbarbutton id="new-identity-button" class="toolbarbutton-1 chromeclass-toolbar-additional"\n'
    '                   label="New Reticulum Identity"\n'
    '                   tooltiptext="Generate a new Reticulum identity"\n'
    '                   data-l10n-id="toolbar-new-identity"/>',
    xhtml
)

# Remove circuit button
xhtml = re.sub(r'<toolbarbutton id="new-circuit-button".*?/>', '', xhtml)

with open(xhtml_path, "w") as f:
    f.write(xhtml)
XHTML_PATCH

# Repackage
python3 -c "
import zipfile, os
with zipfile.ZipFile('$OMNI_B', 'w', zipfile.ZIP_STORED) as z:
    os.chdir('$WORK_B')
    for root, dirs, files in os.walk('.'):
        for f in files:
            path = os.path.join(root, f)
            z.write(path, path[2:])
"

# -------------------------------------------------------------------------
# Step 4: Patch resources/omni.ja
# -------------------------------------------------------------------------
echo "[4/7] Patching resources/omni.ja..."
OMNI_R="$RESOURCES/omni.ja"
WORK_R="/tmp/earth_omni_resources"
rm -rf "$WORK_R" && mkdir -p "$WORK_R"

python3 -c "
import zipfile
with zipfile.ZipFile('$OMNI_R', 'r') as z:
    z.extractall('$WORK_R')
"

# Patch TorLauncherUtil to never start Tor
sed -i '' 's/_getShouldStartAndOwnTor() {/_getShouldStartAndOwnTor() { return false;/' \
    "$WORK_R/modules/TorLauncherUtil.sys.mjs"

# Repackage
python3 -c "
import zipfile, os
with zipfile.ZipFile('$OMNI_R', 'w', zipfile.ZIP_STORED) as z:
    os.chdir('$WORK_R')
    for root, dirs, files in os.walk('.'):
        for f in files:
            path = os.path.join(root, f)
            z.write(path, path[2:])
"

# -------------------------------------------------------------------------
# Step 5: Install preferences
# -------------------------------------------------------------------------
echo "[5/7] Installing preferences..."
PREFS_DIR="$BROWSER_DIR/defaults/pref"
mkdir -p "$PREFS_DIR"
cp "$SCRIPT_DIR/browser/preferences/earth-browser.js" "$PREFS_DIR/"

# -------------------------------------------------------------------------
# Step 6: Bundle earthproxy
# -------------------------------------------------------------------------
echo "[6/7] Bundling earthproxy..."
EARTH_DIR="$BROWSER_DIR/EarthBrowser"
mkdir -p "$EARTH_DIR/rns_config"

cp "$SCRIPT_DIR/earthproxy.py" "$EARTH_DIR/"
cp "$SCRIPT_DIR/earthserv.py" "$EARTH_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$EARTH_DIR/"

# Reticulum config — client only (connects out, doesn't accept incoming)
mkdir -p "$EARTH_DIR/rns_config"
cp "$SCRIPT_DIR/config/client.conf" "$EARTH_DIR/rns_config/config"

# -------------------------------------------------------------------------
# Step 7: Create launcher
# -------------------------------------------------------------------------
echo "[7/7] Creating launcher..."

if [ "$PLATFORM" = "macos" ]; then
    cat > "$BROWSER_DIR/earth-browser" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EARTH_DIR="$SCRIPT_DIR/EarthBrowser"
PROXY_PID=""

export TOR_SKIP_LAUNCH=1
export TOR_PROVIDER=none

cleanup() {
    if [ -n "$PROXY_PID" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        kill "$PROXY_PID" 2>/dev/null
        wait "$PROXY_PID" 2>/dev/null
    fi
}
trap cleanup EXIT

python3 "$EARTH_DIR/earthproxy.py" -c "$EARTH_DIR/rns_config" &
PROXY_PID=$!

for i in $(seq 1 30); do
    python3 -c "
import socket; s = socket.socket(); s.settimeout(1)
try: s.connect(('127.0.0.1', 9150)); s.close(); exit(0)
except: exit(1)
" 2>/dev/null && break
    sleep 0.5
done

"$SCRIPT_DIR/firefox" --purgecaches "http://_earth.ret/welcome" "$@"
LAUNCHER
    chmod +x "$BROWSER_DIR/earth-browser"
fi

# Sign
echo ""
echo "Signing..."
codesign --force --deep --sign - "$OUT" 2>&1 | tail -1

echo ""
echo "=== Done ==="
echo "Earth Browser packaged at: $OUT"
if [ "$PLATFORM" = "macos" ]; then
    echo "Launch: $OUT/Contents/MacOS/earth-browser"
fi
