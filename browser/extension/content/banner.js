"use strict";

/**
 * Content script: injects a persistent warning banner when JS Level 2 (global) is active.
 * Runs on all .ret pages at document_start.
 */

let bannerElement = null;

function showBanner() {
  if (bannerElement) return;
  bannerElement = document.createElement("div");
  bannerElement.id = "earth-browser-js-banner";
  bannerElement.textContent = "\u26A0 JavaScript is globally enabled \u2014 privacy protections degraded";
  // Insert as first child of body when available
  insertBanner();
}

function insertBanner() {
  if (document.body && bannerElement) {
    document.body.insertBefore(bannerElement, document.body.firstChild);
  } else {
    // Body not ready yet, wait
    const observer = new MutationObserver(() => {
      if (document.body) {
        observer.disconnect();
        document.body.insertBefore(bannerElement, document.body.firstChild);
      }
    });
    observer.observe(document.documentElement, { childList: true });
  }
}

function hideBanner() {
  if (bannerElement) {
    bannerElement.remove();
    bannerElement = null;
  }
}

// Check initial state
browser.runtime.sendMessage({ action: "getState", url: window.location.href }).then((state) => {
  if (state && state.jsLevel === 2) {
    showBanner();
  }
});

// Listen for state changes
browser.runtime.onMessage.addListener((msg) => {
  if (msg.action === "stateChanged") {
    if (msg.jsLevel === 2) {
      showBanner();
    } else {
      hideBanner();
    }
  }
});
