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

// Each preview is a separate RGB video: [height, width, 3] per frame.
const videoPreviews = [...document.querySelectorAll("video[data-loop-preview]")];
if (videoPreviews.length !== 2) throw new Error("Expected vision and MABe video previews");

for (const video of videoPreviews) {
  let wantsPlayback = !reducedMotion.matches;
  let inView = false;
  let suspended = true;

  function updateVideoPlayback() {
    suspended = document.hidden || !inView || !wantsPlayback;
    if (suspended) {
      video.pause();
      return;
    }
    video.play().catch(error => {
      // Native controls remain available when the browser blocks autoplay.
      if (error.name !== "NotAllowedError" && error.name !== "AbortError") throw error;
    });
  }

  video.addEventListener("pause", () => {
    if (!suspended) wantsPlayback = false;
  });
  video.addEventListener("play", () => {
    wantsPlayback = true;
    suspended = false;
  });
  new IntersectionObserver(entries => {
    inView = entries[0].isIntersecting;
    updateVideoPlayback();
  }, {threshold: 0.15}).observe(video);
  reducedMotion.addEventListener("change", () => {
    wantsPlayback = !reducedMotion.matches;
    updateVideoPlayback();
  });
  document.addEventListener("visibilitychange", updateVideoPlayback);
  window.addEventListener("pagehide", () => {
    suspended = true;
    video.pause();
  });
  window.addEventListener("pageshow", updateVideoPlayback);
}
