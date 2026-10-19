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

// MARS example video: frames have shape [360 rows, 644 columns, 3 color channels].
const mouseVideo = document.getElementById("mabe-video");
if (!mouseVideo) throw new Error("Missing MABe mouse-tracking preview");
let mouseWantsPlayback = !reducedMotion.matches;
let mouseInView = false;
let mouseSuspended = true;

function updateMousePlayback() {
  mouseSuspended = document.hidden || !mouseInView || !mouseWantsPlayback;
  if (mouseSuspended) {
    mouseVideo.pause();
    return;
  }
  mouseVideo.play().catch(error => {
    // Browsers may block autoplay; native controls still allow explicit playback.
    if (error.name !== "NotAllowedError" && error.name !== "AbortError") throw error;
  });
}

mouseVideo.addEventListener("pause", () => {
  if (!mouseSuspended) mouseWantsPlayback = false;
});
mouseVideo.addEventListener("play", () => {
  mouseWantsPlayback = true;
  mouseSuspended = false;
});
new IntersectionObserver(entries => {
  mouseInView = entries[0].isIntersecting;
  updateMousePlayback();
}, {threshold: 0.15}).observe(mouseVideo);
reducedMotion.addEventListener("change", () => {
  mouseWantsPlayback = !reducedMotion.matches;
  updateMousePlayback();
});
document.addEventListener("visibilitychange", updateMousePlayback);
window.addEventListener("pagehide", () => {
  mouseSuspended = true;
  mouseVideo.pause();
});
window.addEventListener("pageshow", updateMousePlayback);
