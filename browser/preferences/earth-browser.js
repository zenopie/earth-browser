// Earth Browser — Firefox Preference Overrides
//
// These preferences configure Firefox ESR (via Tor Browser) for use with
// the Reticulum network. They handle proxy settings, disable dangerous APIs,
// and maintain all Tor Browser anti-fingerprinting protections.
//
// This file goes in: <firefox>/defaults/pref/earth-browser.js
// or applied via autoconfig.

// =========================================================================
// TOR LAUNCHER — Disable (we use earthproxy instead of Tor)
// =========================================================================

pref("extensions.torlauncher.start_tor", false);
pref("extensions.torlauncher.prompt_at_startup", false);

// Skip the about:torconnect page on startup
pref("torbrowser.settings.quickstart.enabled", true);

// Disable HTTPS-only mode (Reticulum link encryption replaces TLS)
pref("dom.security.https_only_mode", false);
pref("dom.security.https_only_mode_pbm", false);

// Homepage — blank after first run
pref("browser.startup.homepage", "about:blank");

// =========================================================================
// PROXY CONFIGURATION — Route all traffic through earthproxy
// =========================================================================

// Manual proxy config pointing to earthproxy SOCKS5
pref("network.proxy.type", 1);
pref("network.proxy.socks", "127.0.0.1");
pref("network.proxy.socks_port", 9150);
pref("network.proxy.socks_version", 5);
pref("network.proxy.socks_remote_dns", true);
pref("network.proxy.no_proxies_on", "");

// Force all DNS through SOCKS proxy (prevent DNS leaks)
pref("network.dns.disablePrefetch", true);
pref("network.dns.disablePrefetchFromHTTPS", true);
pref("network.prefetch-next", false);

// Disable speculative connections (prevent proxy bypass)
pref("network.http.speculative-parallel-limit", 0);
pref("browser.places.speculativeConnect.enabled", false);

// =========================================================================
// WEBRTC — Always disabled (IP leak vector)
// =========================================================================

pref("media.peerconnection.enabled", false);
pref("media.peerconnection.ice.default_address_only", true);
pref("media.peerconnection.ice.no_host", true);
pref("media.peerconnection.ice.proxy_only", true);
pref("media.navigator.enabled", false);
pref("media.navigator.video.enabled", false);
pref("media.getusermedia.screensharing.enabled", false);
pref("media.getusermedia.audiocapture.enabled", false);

// =========================================================================
// SERVICE WORKERS — Always disabled (persistent background execution)
// =========================================================================

pref("dom.serviceWorkers.enabled", false);

// =========================================================================
// WEB WORKERS — Restricted (side-channel timing attacks)
// =========================================================================

// SharedArrayBuffer enables high-resolution timing attacks
pref("javascript.options.shared_memory", false);

// =========================================================================
// WEBASSEMBLY — Always disabled (native code execution)
// =========================================================================

pref("javascript.options.wasm", false);
pref("javascript.options.wasm_baselinejit", false);
pref("javascript.options.wasm_optimizedjit", false);
pref("javascript.options.wasm_gc", false);

// =========================================================================
// HARDWARE / DEVICE APIs — Always disabled
// =========================================================================

// Geolocation
pref("geo.enabled", false);
pref("geo.wifi.uri", "");

// Notifications
pref("dom.webnotifications.enabled", false);
pref("dom.webnotifications.serviceworker.enabled", false);

// Push
pref("dom.push.enabled", false);
pref("dom.push.connection.enabled", false);
pref("dom.push.serverURL", "");

// Bluetooth
pref("dom.webbluetooth.enabled", false);

// USB
pref("dom.webusb.enabled", false);

// Serial
pref("dom.serial.enabled", false);

// Gamepad (fingerprinting vector)
pref("dom.gamepad.enabled", false);

// VR/XR
pref("dom.vr.enabled", false);
pref("dom.xr.enabled", false);

// Web MIDI
pref("dom.webmidi.enabled", false);

// =========================================================================
// ANTI-FINGERPRINTING (from Tor Browser)
// =========================================================================

// Core fingerprinting resistance
pref("privacy.resistFingerprinting", true);
pref("privacy.resistFingerprinting.letterboxing", true);

// First-party isolation
pref("privacy.firstparty.isolate", true);

// Canvas fingerprinting protection
pref("canvas.capturestream.enabled", false);

// WebGL — limited fingerprinting surface
pref("webgl.disabled", false);
pref("webgl.min_capability_mode", true);
pref("webgl.disable-extensions", true);
pref("webgl.enable-debug-renderer-info", false);

// Font enumeration protection
pref("browser.display.use_document_fonts", 0);
pref("font.system.whitelist", "");

// Timing precision reduction (Spectre/Meltdown mitigation)
pref("privacy.reduceTimerPrecision", true);
pref("privacy.resistFingerprinting.reduceTimerPrecision.microseconds", 100000);

// =========================================================================
// TRACKING & COOKIE PROTECTION
// =========================================================================

pref("privacy.trackingprotection.enabled", true);
pref("privacy.trackingprotection.socialtracking.enabled", true);
pref("network.cookie.cookieBehavior", 1);
pref("network.cookie.lifetimePolicy", 2);
pref("network.cookie.thirdparty.sessionOnly", true);
pref("privacy.clearOnShutdown.cookies", true);
pref("privacy.clearOnShutdown.cache", true);
pref("privacy.clearOnShutdown.sessions", true);
pref("privacy.clearOnShutdown.offlineApps", true);
pref("privacy.clearOnShutdown.siteSettings", false);

// =========================================================================
// STORAGE — Minimize persistent storage
// =========================================================================

pref("dom.indexedDB.enabled", false);
pref("dom.caches.enabled", false);
pref("dom.storage.enabled", true);  // Needed for extension storage

// =========================================================================
// NETWORK SAFETY
// =========================================================================

// Disable beacon API (exfiltration vector)
pref("beacon.enabled", false);

// Disable WebSocket (can bypass proxy in some configs)
pref("network.websocket.enabled", false);

// Disable auto-update and telemetry
pref("app.update.enabled", false);
pref("toolkit.telemetry.enabled", false);
pref("toolkit.telemetry.unified", false);
pref("toolkit.telemetry.archive.enabled", false);
pref("datareporting.policy.dataSubmissionEnabled", false);
pref("datareporting.healthreport.uploadEnabled", false);
pref("browser.ping-centre.telemetry", false);

// Disable safe browsing (phones home to Google)
pref("browser.safebrowsing.malware.enabled", false);
pref("browser.safebrowsing.phishing.enabled", false);
pref("browser.safebrowsing.downloads.enabled", false);
pref("browser.safebrowsing.downloads.remote.enabled", false);

// Disable captive portal detection
pref("network.captive-portal-service.enabled", false);
pref("captivedetect.canonicalURL", "");

// Disable connectivity check
pref("network.connectivity-service.enabled", false);

// =========================================================================
// UI / UX
// =========================================================================

// Homepage
pref("browser.startup.homepage", "about:blank");
pref("browser.startup.page", 0);
pref("browser.newtabpage.enabled", true);

// Disable pocket, snippets, activity stream
pref("extensions.pocket.enabled", false);
pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
pref("browser.newtabpage.activity-stream.feeds.snippets", false);
pref("browser.newtabpage.activity-stream.showSponsored", false);
pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);

// Disable default browser check
pref("browser.shell.checkDefaultBrowser", false);

// Disable form autofill
pref("extensions.formautofill.addresses.enabled", false);
pref("extensions.formautofill.creditCards.enabled", false);

// =========================================================================
// TLS / CERTIFICATE SETTINGS
// =========================================================================

// OCSP — disable (would phone home for .ret sites routed through proxy)
pref("security.OCSP.enabled", 0);

// Disable TLS session tickets (tracking vector)
pref("security.ssl.disable_session_identifiers", true);

// =========================================================================
// MISCELLANEOUS
// =========================================================================

// Disable media autoplay
pref("media.autoplay.default", 5);

// Disable DRM
pref("media.eme.enabled", false);
pref("media.gmp-widevinecdm.enabled", false);

// Disable PDF.js inline viewer (attack surface reduction)
pref("pdfjs.disabled", true);

// Clipboard protection
pref("dom.event.clipboardevents.enabled", false);

// Disable battery API (fingerprinting)
pref("dom.battery.enabled", false);
