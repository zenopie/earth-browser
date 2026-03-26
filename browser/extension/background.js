/**
 * Earth Browser — Background Script
 *
 * Manages JavaScript security levels, per-destination whitelist,
 * CSP injection for script blocking, and shield icon state.
 *
 * JS Levels:
 *   0 = Disabled (default) — scripts blocked on all destinations
 *   1 = Per-destination     — scripts allowed only on whitelisted destinations
 *   2 = Global              — scripts allowed everywhere (degraded privacy)
 */

"use strict";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let jsLevel = 0;                    // Current JS security level
let whitelist = {};                 // { destHash: { permanent: bool } }
let proxyStatus = null;             // Cached status from earthproxy control API
const STORAGE_KEY_LEVEL = "jsLevel";
const STORAGE_KEY_WHITELIST = "jsWhitelist";
const CONTROL_API = "http://_earth.ret";

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

async function init() {
  const stored = await browser.storage.local.get([STORAGE_KEY_LEVEL, STORAGE_KEY_WHITELIST]);
  if (stored[STORAGE_KEY_LEVEL] !== undefined) {
    jsLevel = stored[STORAGE_KEY_LEVEL];
  }
  if (stored[STORAGE_KEY_WHITELIST]) {
    whitelist = stored[STORAGE_KEY_WHITELIST];
  }
  // Strip session-only entries that survived a restart
  cleanSessionEntries();
  await persist();
  updateAllTabIcons();
}

function cleanSessionEntries() {
  for (const hash of Object.keys(whitelist)) {
    if (!whitelist[hash].permanent) {
      delete whitelist[hash];
    }
  }
}

async function persist() {
  await browser.storage.local.set({
    [STORAGE_KEY_LEVEL]: jsLevel,
    [STORAGE_KEY_WHITELIST]: whitelist,
  });
}

// ---------------------------------------------------------------------------
// Destination hash extraction
// ---------------------------------------------------------------------------

function getDestHash(hostname) {
  // hostname looks like: "a4f2b8c91d3e7f06a4f2b8c91d3e7f06.ret"
  if (hostname && hostname.endsWith(".ret")) {
    return hostname.slice(0, -4).toLowerCase();
  }
  return null;
}

function isRetAddress(url) {
  try {
    return new URL(url).hostname.endsWith(".ret");
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// JS permission logic
// ---------------------------------------------------------------------------

function isJSAllowed(destHash) {
  if (jsLevel === 0) return false;
  if (jsLevel === 2) return true;
  // Level 1: check whitelist
  return destHash !== null && destHash in whitelist;
}

// ---------------------------------------------------------------------------
// CSP injection — blocks scripts on non-permitted destinations
// ---------------------------------------------------------------------------

browser.webRequest.onHeadersReceived.addListener(
  (details) => {
    if (details.type !== "main_frame" && details.type !== "sub_frame") {
      // Only inject CSP on document loads, not subresources
      // (CSP on the document already governs subresource loading)
      return {};
    }

    const url = details.url;
    const destHash = getDestHash(new URL(url).hostname);

    const headers = details.responseHeaders || [];

    if (!isJSAllowed(destHash)) {
      // Block all scripts and workers
      headers.push({
        name: "Content-Security-Policy",
        value: "script-src 'none'; worker-src 'none'; object-src 'none';",
      });
    } else {
      // JS allowed but still block workers (always disabled)
      headers.push({
        name: "Content-Security-Policy",
        value: "worker-src 'none'; object-src 'none';",
      });
    }

    return { responseHeaders: headers };
  },
  { urls: ["<all_urls>"] },
  ["blocking", "responseHeaders"]
);

// ---------------------------------------------------------------------------
// Block dangerous request types regardless of JS level
// ---------------------------------------------------------------------------

browser.webRequest.onBeforeRequest.addListener(
  (details) => {
    const type = details.type;

    // Always block WebSocket/WebRTC/beacon to non-.ret destinations
    if (type === "websocket" || type === "beacon" || type === "csp_report") {
      if (!isRetAddress(details.url)) {
        return { cancel: true };
      }
    }

    // Block Service Worker registration attempts
    if (type === "script" && details.url.includes("serviceworker")) {
      return { cancel: true };
    }

    return {};
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);

// Block requests from .ret pages to non-.ret destinations (prevent clearnet leaks)
browser.webRequest.onBeforeRequest.addListener(
  (details) => {
    // Only applies to requests initiated by a .ret page
    if (details.originUrl && isRetAddress(details.originUrl)) {
      if (!isRetAddress(details.url)) {
        // Allow extension resources
        if (details.url.startsWith("moz-extension://")) return {};
        console.log(`[Earth Browser] Blocked clearnet request from .ret page: ${details.url}`);
        return { cancel: true };
      }
    }
    return {};
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);

// ---------------------------------------------------------------------------
// Shield icon management
// ---------------------------------------------------------------------------

function getShieldColor(destHash) {
  if (jsLevel === 2) return "red";
  if (jsLevel === 1 && destHash && destHash in whitelist) return "yellow";
  return "green";
}

function getShieldTitle(color) {
  switch (color) {
    case "green":  return "Earth Browser — JS Disabled";
    case "yellow": return "Earth Browser — JS Enabled (this destination)";
    case "red":    return "Earth Browser — JS Globally Enabled (privacy degraded)";
  }
}

async function updateTabIcon(tabId) {
  try {
    const tab = await browser.tabs.get(tabId);
    if (!tab.url) return;

    const destHash = getDestHash(new URL(tab.url).hostname);
    const color = getShieldColor(destHash);

    browser.browserAction.setIcon({
      tabId,
      path: {
        16: `icons/shield-${color}-16.svg`,
        32: `icons/shield-${color}-32.svg`,
      },
    });
    browser.browserAction.setTitle({
      tabId,
      title: getShieldTitle(color),
    });
  } catch {
    // Tab may have been closed
  }
}

async function updateAllTabIcons() {
  const tabs = await browser.tabs.query({});
  for (const tab of tabs) {
    updateTabIcon(tab.id);
  }
}

browser.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url || changeInfo.status === "complete") {
    updateTabIcon(tabId);
  }
});

browser.tabs.onActivated.addListener((activeInfo) => {
  updateTabIcon(activeInfo.tabId);
});

// ---------------------------------------------------------------------------
// Message API — for popup, options, and content scripts
// ---------------------------------------------------------------------------

browser.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.action) {
    case "getState": {
      let destHash = null;
      if (msg.url) {
        destHash = getDestHash(new URL(msg.url).hostname);
      }
      sendResponse({
        jsLevel,
        whitelist,
        destHash,
        jsAllowed: isJSAllowed(destHash),
        shieldColor: getShieldColor(destHash),
      });
      return;
    }

    case "setJSLevel": {
      jsLevel = msg.level;
      persist();
      updateAllTabIcons();
      notifyContentScripts();
      sendResponse({ ok: true });
      return;
    }

    case "whitelistAdd": {
      whitelist[msg.destHash] = { permanent: !!msg.permanent };
      persist();
      updateAllTabIcons();
      notifyContentScripts();
      // Reload the tab to apply new CSP
      if (msg.tabId) {
        browser.tabs.reload(msg.tabId);
      }
      sendResponse({ ok: true });
      return;
    }

    case "whitelistRemove": {
      delete whitelist[msg.destHash];
      persist();
      updateAllTabIcons();
      notifyContentScripts();
      if (msg.tabId) {
        browser.tabs.reload(msg.tabId);
      }
      sendResponse({ ok: true });
      return;
    }

    case "getWhitelist": {
      sendResponse({ whitelist });
      return;
    }
  }
});

async function notifyContentScripts() {
  const tabs = await browser.tabs.query({});
  for (const tab of tabs) {
    try {
      browser.tabs.sendMessage(tab.id, {
        action: "stateChanged",
        jsLevel,
      });
    } catch {
      // Content script may not be loaded
    }
  }
}

// ---------------------------------------------------------------------------
// Proxy status polling — checks earthproxy control API periodically
// ---------------------------------------------------------------------------

async function pollProxyStatus() {
  try {
    const resp = await fetch(`${CONTROL_API}/status`, { method: "GET" });
    proxyStatus = await resp.json();
  } catch {
    proxyStatus = { running: false, privacy_mode: "unknown", reticulum: false };
  }
}

async function setPrivacyMode(mode) {
  try {
    const resp = await fetch(`${CONTROL_API}/privacy-mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    const result = await resp.json();
    if (result.ok) {
      await pollProxyStatus();
    }
    return result;
  } catch {
    return { error: "proxy not reachable" };
  }
}

async function pinIdentity(destHash) {
  try {
    const resp = await fetch(`${CONTROL_API}/pin-identity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dest_hash: destHash }),
    });
    return await resp.json();
  } catch {
    return { error: "proxy not reachable" };
  }
}

async function unpinIdentity(destHash) {
  try {
    const resp = await fetch(`${CONTROL_API}/pin-identity/${destHash}`, {
      method: "DELETE",
    });
    return await resp.json();
  } catch {
    return { error: "proxy not reachable" };
  }
}

async function newIdentity() {
  try {
    const resp = await fetch(`${CONTROL_API}/new-identity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const result = await resp.json();
    if (result.ok) {
      await pollProxyStatus();
    }
    return result;
  } catch {
    return { error: "proxy not reachable" };
  }
}

// Poll every 5 seconds
setInterval(pollProxyStatus, 5000);

// ---------------------------------------------------------------------------
// Extended message API — proxy status and privacy mode
// ---------------------------------------------------------------------------

const baseListener = browser.runtime.onMessage.hasListener;

// Extend the existing message listener with proxy commands
const originalListener = browser.runtime.onMessage._listeners;

browser.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.action) {
    case "getProxyStatus": {
      if (proxyStatus) {
        sendResponse(proxyStatus);
      } else {
        pollProxyStatus().then(() => sendResponse(proxyStatus));
        return true; // async response
      }
      return;
    }

    case "setPrivacyMode": {
      setPrivacyMode(msg.mode).then(sendResponse);
      return true; // async response
    }

    case "pinIdentity": {
      pinIdentity(msg.destHash).then(sendResponse);
      return true;
    }

    case "unpinIdentity": {
      unpinIdentity(msg.destHash).then(sendResponse);
      return true;
    }

    case "newIdentity": {
      newIdentity().then(sendResponse);
      return true;
    }
  }
});

// ---------------------------------------------------------------------------
// First-run detection
// ---------------------------------------------------------------------------

async function checkFirstRun() {
  const data = await browser.storage.local.get("firstRunComplete");
  if (!data.firstRunComplete) {
    browser.tabs.create({ url: browser.runtime.getURL("pages/welcome.html") });
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

init();
pollProxyStatus();
checkFirstRun();
