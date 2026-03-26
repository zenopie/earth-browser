"use strict";

let selectedMode = "ephemeral_session";

function showStep(n) {
  document.getElementById("step1").classList.toggle("hidden", n !== 1);
  document.getElementById("step2").classList.toggle("hidden", n !== 2);
  document.getElementById("step3").classList.toggle("hidden", n !== 3);
}

function selectMode(el, mode) {
  selectedMode = mode;
  document.querySelectorAll(".mode-option").forEach((o) => o.classList.remove("selected"));
  el.classList.add("selected");
  el.querySelector("input").checked = true;
}

// Wire up mode option clicks
document.querySelectorAll(".mode-option").forEach((el) => {
  el.addEventListener("click", () => {
    const input = el.querySelector("input");
    selectMode(el, input.value);
  });
});

// Wire up navigation buttons
document.getElementById("btn-step2").addEventListener("click", () => showStep(2));
document.getElementById("btn-step3").addEventListener("click", () => showStep(3));

document.getElementById("btn-finish").addEventListener("click", async () => {
  try {
    await browser.runtime.sendMessage({ action: "setPrivacyMode", mode: selectedMode });
  } catch {
    // Proxy may not be running yet
  }

  await browser.storage.local.set({ firstRunComplete: true });
  window.location.href = "newtab.html";
});

// If first-run already done, redirect to new tab
browser.storage.local.get("firstRunComplete").then((data) => {
  if (data.firstRunComplete) {
    window.location.href = "newtab.html";
  }
});
