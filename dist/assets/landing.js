"use strict";

// Sprite shape: [32 rows, 20 frames × 64 columns]. Each frame fills the preview.
const preview = document.getElementById("realpde-preview");
const toggle = document.getElementById("realpde-preview-toggle");
if (!preview || !toggle) throw new Error("Missing RealPDE preview or playback control");

const frameCount = 20;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let wantsPlayback = !reducedMotion.matches;
let frame = 0;
let timer = null;

function updatePlayback() {
  clearInterval(timer);
  timer = null;
  toggle.textContent = wantsPlayback ? "Pause animation" : "Play animation";
  if (!wantsPlayback || document.hidden) return;
  timer = setInterval(() => {
    frame = (frame + 1) % frameCount;
    preview.style.transform = `translateX(-${frame * 100 / frameCount}%)`;
  }, 100); // 10 FPS, matching the article's forecast playback.
}

preview.decode().then(() => {
  if (preview.naturalWidth !== 1280 || preview.naturalHeight !== 32) {
    throw new Error("Expected a 20-frame RealPDE sprite with 64 × 32 fields");
  }
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    wantsPlayback = !wantsPlayback;
    updatePlayback();
  });
  reducedMotion.addEventListener("change", () => {
    wantsPlayback = !reducedMotion.matches;
    updatePlayback();
  });
  document.addEventListener("visibilitychange", updatePlayback);
  window.addEventListener("pagehide", () => clearInterval(timer));
  window.addEventListener("pageshow", updatePlayback);
  updatePlayback();
});
