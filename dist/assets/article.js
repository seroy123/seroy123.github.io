"use strict";

// Each chapter initializes only the interactive components it contains.
function required(id) {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing interactive article element: ${id}`);
  return element;
}

if (document.getElementById("forecast-gallery")) {
  const slider = required("forecast-horizon");
  const label = required("forecast-time");
  const button = required("forecast-play");
  const strips = [...document.querySelectorAll(".forecast-strip")];
  if (strips.length !== 12) throw new Error("Expected three panels for each of four forecasts");
  let timer = null;
  const render = () => {
    const frame = Number(slider.value);
    if (!Number.isInteger(frame) || frame < 1 || frame > 20) throw new Error("Invalid forecast frame");
    // Sprite shape: 32 rows × (20 frames × 64 columns). Translation uses image width.
    for (const strip of strips) strip.style.transform = `translateX(-${(frame - 1) * 5}%)`;
    label.value = `+${frame}`;
    slider.setAttribute("aria-valuetext", `${frame} frames ahead`);
  };
  const pause = () => {
    clearInterval(timer);
    timer = null;
    button.textContent = "Play forecast";
    button.setAttribute("aria-pressed", "false");
  };
  slider.addEventListener("input", () => { pause(); render(); });
  button.addEventListener("click", () => {
    if (timer !== null) { pause(); return; }
    button.textContent = "Pause forecast";
    button.setAttribute("aria-pressed", "true");
    timer = setInterval(() => {
      slider.value = String(Number(slider.value) % 20 + 1);
      render();
    }, 100); // 10 FPS; all forecast panels advance together.
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  window.addEventListener("pagehide", pause);
  render();
}

if (document.querySelector("[data-crop-explorer]")) {
  const input = required("crop-input-image");
  const target = required("crop-target-image");
  const left = required("crop-x");
  const top = required("crop-y");
  const canvases = ["crop-source", "crop-result", "crop-target"].map(required);
  const contexts = canvases.map(canvas => {
    const context = canvas.getContext("2d");
    if (!context) throw new Error("This browser cannot draw the crop explorer");
    context.imageSmoothingEnabled = false;
    return context;
  });
  const render = () => {
    const x = Number(left.value), y = Number(top.value);
    if (x < 0 || x > 64 || y < 0 || y > 32) throw new Error("Crop exceeds the raw field");
    required("crop-x-label").value = String(x);
    required("crop-y-label").value = String(y);
    // Raw field shape: [64, 128]; contiguous crop shape: [32, 64], displayed enlarged.
    contexts[0].drawImage(input, 0, 0, 768, 384);
    contexts[0].strokeStyle = "#ffffff";
    contexts[0].lineWidth = 4;
    contexts[0].strokeRect(x * 6 + 2, y * 6 + 2, 380, 188);
    contexts[1].drawImage(input, x, y, 64, 32, 0, 0, 512, 256);
    contexts[2].drawImage(target, x, y, 64, 32, 0, 0, 512, 256);
  };
  Promise.all([input.decode(), target.decode()]).then(() => {
    if ([input, target].some(image => image.naturalWidth !== 128 || image.naturalHeight !== 64)) {
      throw new Error("Unexpected crop source dimensions");
    }
    left.addEventListener("input", render);
    top.addEventListener("input", render);
    render();
  }).catch(error => {
    const message = document.createElement("p");
    message.textContent = "The crop explorer could not load. The static comparison above shows the same operation.";
    message.setAttribute("role", "alert");
    document.querySelector("[data-crop-explorer]").append(message);
    throw error;
  });
}

// Each augmentation uses its own synchronized sequence and 10 FPS playback.
function bindSequencePlayback(container, prefix, expectedPanels) {
  const slider = required(`${prefix}-frame`);
  const label = required(`${prefix}-time`);
  const button = required(`${prefix}-play`);
  const strips = [...container.querySelectorAll('.augmentation-strip')];
  if (strips.length !== expectedPanels) throw new Error(`Incomplete ${prefix} animation`);
  let timer = null;
  const render = () => {
    const frame = Number(slider.value);
    if (!Number.isInteger(frame) || frame < 1 || frame > 20) throw new Error('Invalid animation frame');
    // Sprite shape: 32 rows × (20 frames × 64 columns), shared time across panels.
    for (const strip of strips) strip.style.transform = `translateX(-${(frame - 1) * 5}%)`;
    label.value = String(frame);
    slider.setAttribute('aria-valuetext', `Frame ${frame} of 20`);
  };
  const pause = () => {
    clearInterval(timer);
    timer = null;
    button.textContent = `Play ${prefix}`;
    button.setAttribute('aria-pressed', 'false');
  };
  button.addEventListener('click', () => {
    if (timer !== null) { pause(); return; }
    if (Number(slider.value) === 20) { slider.value = '1'; render(); }
    button.textContent = `Pause ${prefix}`;
    button.setAttribute('aria-pressed', 'true');
    timer = setInterval(() => {
      slider.value = String(Number(slider.value) % 20 + 1);
      render();
    }, 100);
  });
  slider.addEventListener('input', () => { pause(); render(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
  window.addEventListener('pagehide', pause);
  const chapter = container.closest('.solution-chapter');
  if (chapter) chapter.addEventListener('toggle', () => { if (!chapter.open) pause(); });
  render();
}

const mixup = document.querySelector('[data-mixup-explorer]');
if (mixup) {
  bindSequencePlayback(mixup, 'mixup', 6);
  const slider = required('mixup-weight');
  const images = [required('mixup-input'), required('mixup-target')];
  const paths = images.map(image => image.getAttribute('src'));
  const renderWeight = () => {
    const weight = Number(slider.value);
    if (weight < 50 || weight > 100 || weight % 5 !== 0) throw new Error('Unsupported mixup weight');
    required('mixup-label').value = (weight / 100).toFixed(2);
    slider.setAttribute('aria-valuetext', `${weight}% window A, ${100 - weight}% window B`);
    images.forEach((image, index) => {
      image.src = paths[index].replace(/75-sequence\.png$/, `${weight}-sequence.png`);
    });
  };
  slider.addEventListener('input', renderWeight);
  renderWeight();
}
const reflection = document.querySelector('[data-reflection-explorer]');
if (reflection) bindSequencePlayback(reflection, 'reflection', 3);

// Deep links reveal their chapter and any nested evidence before scrolling.
function revealSection(hash, focus = false) {
  if (!hash || hash === '#') return;
  const target = document.getElementById(decodeURIComponent(hash.slice(1)));
  if (!target) return;
  let ancestor = target;
  while (ancestor) {
    if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
    ancestor = ancestor.parentElement;
  }
  requestAnimationFrame(() => {
    target.scrollIntoView({block: 'start', behavior: 'instant'});
    if (focus && target instanceof HTMLDetailsElement) {
      target.querySelector('summary').focus({preventScroll: true});
    }
  });
}
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const hash = link.getAttribute('href');
  if (!document.getElementById(decodeURIComponent(hash.slice(1)))) return;
  event.preventDefault();
  if (location.hash !== hash) history.pushState(null, '', hash);
  revealSection(hash, true);
});
window.addEventListener('hashchange', () => revealSection(location.hash));
window.addEventListener('popstate', () => revealSection(location.hash));
revealSection(location.hash);
