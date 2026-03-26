"use strict";

let state = {};

async function loadState() {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  const url = tab ? tab.url : "";
  state = await browser.runtime.sendMessage({ action: "getState", url });
  state.tabId = tab ? tab.id : null;
  state.url = url;
  render();
}

function render() {
  // Shield icon
  const shield = document.getElementById("shield-icon");
  shield.className = state.shieldColor;

  // Status text
  const statusText = document.getElementById("status-text");
  switch (state.shieldColor) {
    case "green":
      statusText.textContent = "JavaScript Disabled";
      break;
    case "yellow":
      statusText.textContent = "JavaScript Enabled (this destination)";
      break;
    case "red":
      statusText.textContent = "JavaScript Globally Enabled";
      break;
  }

  // Destination info
  const destInfo = document.getElementById("dest-info");
  const destHashEl = document.getElementById("dest-hash");
  if (state.destHash) {
    destInfo.classList.remove("hidden");
    destHashEl.textContent = state.destHash;
  } else {
    destInfo.classList.add("hidden");
  }

  // Level buttons
  document.getElementById("btn-level0").classList.toggle("active", state.jsLevel === 0);
  document.getElementById("btn-level1").classList.toggle("active", state.jsLevel === 1);
  document.getElementById("btn-level2").classList.toggle("active", state.jsLevel === 2);

  // Whitelist section (only show for Level 1 on .ret pages)
  const whitelistSection = document.getElementById("whitelist-section");
  const whitelistBtn = document.getElementById("btn-whitelist-toggle");
  if (state.jsLevel === 1 && state.destHash) {
    whitelistSection.classList.remove("hidden");
    if (state.destHash in (state.whitelist || {})) {
      whitelistBtn.textContent = "Disable JavaScript for this destination";
      whitelistBtn.className = "action-btn";
    } else {
      whitelistBtn.textContent = "Enable JavaScript for this destination";
      whitelistBtn.className = "action-btn warn";
    }
  } else {
    whitelistSection.classList.add("hidden");
  }
}

// Level buttons
document.getElementById("btn-level0").addEventListener("click", async () => {
  await browser.runtime.sendMessage({ action: "setJSLevel", level: 0 });
  await loadState();
});

document.getElementById("btn-level1").addEventListener("click", async () => {
  await browser.runtime.sendMessage({ action: "setJSLevel", level: 1 });
  await loadState();
});

document.getElementById("btn-level2").addEventListener("click", () => {
  // Show Level 2 warning
  document.getElementById("confirm-l2").classList.remove("hidden");
});

// Level 2 confirmation
document.getElementById("btn-l2-confirm").addEventListener("click", async () => {
  await browser.runtime.sendMessage({ action: "setJSLevel", level: 2 });
  document.getElementById("confirm-l2").classList.add("hidden");
  await loadState();
});

document.getElementById("btn-l2-cancel").addEventListener("click", () => {
  document.getElementById("confirm-l2").classList.add("hidden");
});

// Whitelist toggle
document.getElementById("btn-whitelist-toggle").addEventListener("click", () => {
  if (!state.destHash) return;

  if (state.destHash in (state.whitelist || {})) {
    // Remove from whitelist
    browser.runtime.sendMessage({
      action: "whitelistRemove",
      destHash: state.destHash,
      tabId: state.tabId,
    }).then(loadState);
  } else {
    // Show Level 1 warning
    document.getElementById("confirm-dest").textContent = state.destHash;
    document.getElementById("confirm-l1").classList.remove("hidden");
  }
});

// Level 1 whitelist confirmation
document.getElementById("btn-l1-session").addEventListener("click", async () => {
  await browser.runtime.sendMessage({
    action: "whitelistAdd",
    destHash: state.destHash,
    permanent: false,
    tabId: state.tabId,
  });
  document.getElementById("confirm-l1").classList.add("hidden");
  await loadState();
});

document.getElementById("btn-l1-permanent").addEventListener("click", async () => {
  await browser.runtime.sendMessage({
    action: "whitelistAdd",
    destHash: state.destHash,
    permanent: true,
    tabId: state.tabId,
  });
  document.getElementById("confirm-l1").classList.add("hidden");
  await loadState();
});

document.getElementById("btn-l1-cancel").addEventListener("click", () => {
  document.getElementById("confirm-l1").classList.add("hidden");
});

// Options
document.getElementById("btn-options").addEventListener("click", () => {
  browser.runtime.openOptionsPage();
});

// New Identity button
document.getElementById("btn-new-identity").addEventListener("click", async () => {
  const result = await browser.runtime.sendMessage({ action: "newIdentity" });
  if (result && result.ok) {
    const hashEl = document.getElementById("identity-hash");
    hashEl.textContent = result.identity_hash;
    hashEl.classList.remove("hidden");
    // Reload all tabs to use new identity
    const tabs = await browser.tabs.query({});
    for (const tab of tabs) {
      if (tab.url && tab.url.includes(".ret")) {
        browser.tabs.reload(tab.id);
      }
    }
  }
});

// Privacy mode selector
document.getElementById("privacy-mode-select").addEventListener("change", async (e) => {
  const mode = e.target.value;
  await browser.runtime.sendMessage({ action: "setPrivacyMode", mode });
  await loadProxyStatus();
});

// Proxy status
async function loadProxyStatus() {
  const status = await browser.runtime.sendMessage({ action: "getProxyStatus" });
  const indicator = document.getElementById("proxy-indicator");
  const statusText = document.getElementById("proxy-status-text");
  const modeRow = document.getElementById("privacy-mode-row");
  const modeSelect = document.getElementById("privacy-mode-select");

  if (status && status.running) {
    indicator.className = "indicator on";
    statusText.textContent = "Connected";
    modeRow.classList.remove("hidden");
    modeSelect.value = status.privacy_mode;
  } else {
    indicator.className = "indicator off";
    statusText.textContent = "earthproxy not running";
    modeRow.classList.add("hidden");
  }
}

// Show current identity hash
async function loadIdentity() {
  const status = await browser.runtime.sendMessage({ action: "getProxyStatus" });
  if (status && status.identity_hash) {
    const hashEl = document.getElementById("identity-hash");
    hashEl.textContent = status.identity_hash;
    hashEl.classList.remove("hidden");
  }
}

loadState();
loadProxyStatus();
loadIdentity();
