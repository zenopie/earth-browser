"use strict";

/* eslint-env mozilla/browser-window */

var SecurityLevelButton = {
  _button: null,
  _anchorButton: null,

  _configUIFromPrefs() {
    this._button.setAttribute("level", "safest");
  },

  openPopup() {
    const overflowPanel = document.getElementById("widget-overflow");
    if (overflowPanel.contains(this._button)) {
      overflowPanel.hidePopup();
      this._anchorButton = document.getElementById("nav-bar-overflow-button");
    } else {
      this._anchorButton = this._button;
    }
    SecurityLevelPanel.show(this._anchorButton);
  },

  init() {
    this._button =
      document.getElementById("security-level-button") ||
      window.gNavToolbox.palette.querySelector("#security-level-button");
    this._button.addEventListener("command", () => this.openPopup());
    this._configUIFromPrefs();
    SecurityLevelPanel.init();
  },

  uninit() { SecurityLevelPanel.uninit(); },
  observe() {},
};

var SecurityLevelPanel = {
  _panel: null,
  _identityEl: null,
  _modeEl: null,
  _jsLevelEl: null,
  _whitelistSection: null,
  _whitelistToggle: null,
  _currentDestEl: null,
  _updating: false,
  _proxyData: null,

  init() {
    this._panel = document.getElementById("securityLevel-panel");
    this._identityEl = document.getElementById("earth-identity-hash");
    this._modeEl = document.getElementById("earth-privacy-mode");
    this._jsLevelEl = document.getElementById("earth-js-level");
    this._whitelistSection = document.getElementById("earth-whitelist-section");
    this._whitelistToggle = document.getElementById("earth-whitelist-toggle");
    this._currentDestEl = document.getElementById("earth-current-dest");

    if (this._jsLevelEl) {
      this._jsLevelEl.addEventListener("select", () => {
        if (!this._updating) {
          const level = parseInt(this._jsLevelEl.value);
          this._onJSLevelChange(level);
        }
      });
    }

    if (this._modeEl) {
      this._modeEl.addEventListener("select", () => {
        if (!this._updating) {
          this._setPrivacyMode(this._modeEl.value);
        }
      });
    }

    if (this._whitelistToggle) {
      this._whitelistToggle.addEventListener("command", () => this._toggleWhitelist());
    }

    if (this._panel) {
      this._panel.addEventListener("popupshown", () => this._fetchStatus());
    }
  },

  uninit() {},

  show(anchor) {
    if (this._panel) {
      this._panel.openPopup(anchor.icon || anchor, "bottomright topright", 0, 0, false);
    }
  },

  hide() {
    if (this._panel) {
      this._panel.hidePopup();
    }
  },

  _getCurrentDestHash() {
    try {
      const browser = window.gBrowser.selectedBrowser;
      const url = new URL(browser.currentURI.spec);
      const host = url.hostname;
      if (host.endsWith(".ret")) {
        return host.slice(0, -4).toLowerCase();
      }
    } catch (e) {}
    return null;
  },

  async _fetchStatus() {
    this._updating = true;
    try {
      const resp = await fetch("http://_earth.ret/status");
      this._proxyData = await resp.json();
      if (this._identityEl) {
        this._identityEl.textContent = this._proxyData.identity_hash || "unknown";
      }
      if (this._modeEl) {
        this._modeEl.value = this._proxyData.privacy_mode || "ephemeral_session";
      }
      if (this._jsLevelEl) {
        this._jsLevelEl.value = String(this._proxyData.js_level || 0);
      }
    } catch (e) {
      if (this._identityEl) this._identityEl.textContent = "Proxy not connected";
      this._proxyData = null;
    }

    this._updateWhitelistUI();
    this._updating = false;
  },

  _updateWhitelistUI() {
    const destHash = this._getCurrentDestHash();
    const jsLevel = this._proxyData ? this._proxyData.js_level : 0;
    const whitelist = this._proxyData ? (this._proxyData.js_whitelist || []) : [];

    if (jsLevel === 1 && destHash) {
      this._whitelistSection.hidden = false;
      this._currentDestEl.textContent = destHash;
      const isWhitelisted = whitelist.includes(destHash);
      this._whitelistToggle.setAttribute("label",
        isWhitelisted ? "Disable JS for this destination" : "Enable JS for this destination"
      );
    } else {
      this._whitelistSection.hidden = true;
    }
  },

  async _onJSLevelChange(level) {
    // Warning dialog for Level 2
    if (level === 2) {
      const confirmed = Services.prompt.confirm(
        window,
        "Global JavaScript",
        "You are enabling JavaScript for ALL destinations.\n\n" +
        "This significantly degrades your privacy. Any destination can:\n" +
        "- Fingerprint your browser and hardware\n" +
        "- Execute arbitrary code\n" +
        "- Attempt data exfiltration\n" +
        "- Correlate your identity across destinations\n\n" +
        "Reticulum transport encryption remains active, but JavaScript " +
        "can undermine endpoint protections.\n\n" +
        "Continue?"
      );
      if (!confirmed) {
        this._updating = true;
        this._jsLevelEl.value = String(this._proxyData ? this._proxyData.js_level : 0);
        this._updating = false;
        return;
      }
    }

    Services.prefs.setIntPref("earthbrowser.js_level", level);
    await this._setJSLevel(level);
    this._updateWhitelistUI();
  },

  async _toggleWhitelist() {
    const destHash = this._getCurrentDestHash();
    if (!destHash) return;

    const whitelist = this._proxyData ? (this._proxyData.js_whitelist || []) : [];
    const isWhitelisted = whitelist.includes(destHash);

    if (!isWhitelisted) {
      // Warning before enabling JS for a destination
      const confirmed = Services.prompt.confirm(
        window,
        "Enable JavaScript",
        "Enable JavaScript for this destination?\n\n" +
        `Destination: ${destHash}\n\n` +
        "This allows the destination to:\n" +
        "- Run arbitrary code on your machine\n" +
        "- Fingerprint your browser and hardware\n" +
        "- Track you across page loads via storage\n\n" +
        "Reticulum protects your transport. JavaScript bypasses " +
        "that protection at the endpoint.\n\n" +
        "Continue?"
      );
      if (!confirmed) return;
    }

    try {
      await fetch("http://_earth.ret/js-whitelist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: isWhitelisted ? "remove" : "add",
          dest_hash: destHash,
        }),
      });
      await this._fetchStatus();
      // Reload to apply new CSP
      window.gBrowser.selectedBrowser.reload();
    } catch (e) {}
  },

  async _setJSLevel(level) {
    try {
      await fetch("http://_earth.ret/js-level", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level }),
      });
    } catch (e) {}
  },

  async _setPrivacyMode(mode) {
    try {
      await fetch("http://_earth.ret/privacy-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      this._fetchStatus();
    } catch (e) {}
  },

  openSecuritySettings() { this.hide(); },
  observe() {},
};

var SecurityLevelPreferences = {
  init() {},
  uninit() {},
  observe() {},
};
