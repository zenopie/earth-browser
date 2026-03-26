"use strict";

async function loadState() {
  const state = await browser.runtime.sendMessage({ action: "getState", url: "" });
  const { whitelist } = await browser.runtime.sendMessage({ action: "getWhitelist" });

  // JS Level radio buttons
  document.querySelectorAll('input[name="jsLevel"]').forEach((radio) => {
    radio.checked = parseInt(radio.value) === state.jsLevel;
  });

  // Whitelist section visibility
  const whitelistSection = document.getElementById("whitelist-section");
  whitelistSection.style.display = state.jsLevel === 1 ? "" : "none";

  // Render whitelist entries
  const listEl = document.getElementById("whitelist-list");
  const emptyEl = document.getElementById("whitelist-empty");
  listEl.innerHTML = "";

  const entries = Object.entries(whitelist || {});
  if (entries.length === 0) {
    emptyEl.style.display = "";
  } else {
    emptyEl.style.display = "none";
    for (const [hash, info] of entries) {
      const row = document.createElement("div");
      row.className = "whitelist-entry";

      const left = document.createElement("div");
      const hashSpan = document.createElement("span");
      hashSpan.className = "whitelist-hash";
      hashSpan.textContent = hash;
      left.appendChild(hashSpan);

      const typeSpan = document.createElement("span");
      typeSpan.className = "whitelist-type";
      typeSpan.textContent = info.permanent ? "(permanent)" : "(session only)";
      left.appendChild(typeSpan);

      const removeBtn = document.createElement("button");
      removeBtn.className = "whitelist-remove";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", async () => {
        await browser.runtime.sendMessage({ action: "whitelistRemove", destHash: hash });
        loadState();
      });

      row.appendChild(left);
      row.appendChild(removeBtn);
      listEl.appendChild(row);
    }
  }
}

// JS Level change
document.querySelectorAll('input[name="jsLevel"]').forEach((radio) => {
  radio.addEventListener("change", async (e) => {
    const level = parseInt(e.target.value);
    await browser.runtime.sendMessage({ action: "setJSLevel", level });
    loadState();
  });
});

// ---------------------------------------------------------------------------
// Proxy status and privacy mode
// ---------------------------------------------------------------------------

async function loadProxyStatus() {
  const status = await browser.runtime.sendMessage({ action: "getProxyStatus" });
  const indicator = document.getElementById("proxy-indicator");
  const statusText = document.getElementById("proxy-status-text");
  const modeSection = document.getElementById("privacy-mode-section");
  const pinnedSection = document.getElementById("pinned-section");
  const statsSection = document.getElementById("proxy-stats");

  if (status && status.running) {
    indicator.className = "indicator on";
    statusText.textContent = "Connected — Reticulum active";
    modeSection.classList.remove("hidden");
    statsSection.classList.remove("hidden");

    // Privacy mode radios
    document.querySelectorAll('input[name="privacyMode"]').forEach((radio) => {
      radio.checked = radio.value === status.privacy_mode;
    });

    // Show pinned section only in pinned mode
    if (status.privacy_mode === "pinned") {
      pinnedSection.classList.remove("hidden");
      renderPinnedList(status.pinned_destinations || []);
    } else {
      pinnedSection.classList.add("hidden");
    }

    // Stats
    document.getElementById("stat-connections").textContent = status.active_connections || 0;
    document.getElementById("stat-total").textContent = status.total_requests || 0;
  } else {
    indicator.className = "indicator off";
    statusText.textContent = "earthproxy not running";
    modeSection.classList.add("hidden");
    pinnedSection.classList.add("hidden");
    statsSection.classList.add("hidden");
  }
}

function renderPinnedList(destinations) {
  const listEl = document.getElementById("pinned-list");
  const emptyEl = document.getElementById("pinned-empty");
  listEl.innerHTML = "";

  if (destinations.length === 0) {
    emptyEl.style.display = "";
  } else {
    emptyEl.style.display = "none";
    for (const hash of destinations) {
      const row = document.createElement("div");
      row.className = "pinned-entry";

      const hashSpan = document.createElement("span");
      hashSpan.className = "pinned-hash";
      hashSpan.textContent = hash;

      const removeBtn = document.createElement("button");
      removeBtn.className = "pinned-remove";
      removeBtn.textContent = "Unpin";
      removeBtn.addEventListener("click", async () => {
        await browser.runtime.sendMessage({ action: "unpinIdentity", destHash: hash });
        loadProxyStatus();
      });

      row.appendChild(hashSpan);
      row.appendChild(removeBtn);
      listEl.appendChild(row);
    }
  }
}

// Privacy mode change
document.querySelectorAll('input[name="privacyMode"]').forEach((radio) => {
  radio.addEventListener("change", async (e) => {
    await browser.runtime.sendMessage({ action: "setPrivacyMode", mode: e.target.value });
    loadProxyStatus();
  });
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

loadState();
loadProxyStatus();

// Refresh proxy status periodically while options page is open
setInterval(loadProxyStatus, 5000);
