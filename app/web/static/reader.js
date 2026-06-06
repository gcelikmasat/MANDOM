// Immersive paged reader. Click the side zones or use arrow keys; direction-aware
// so right-to-left manga turns the natural way. Falls through to the previous /
// next chapter at the ends.
(function () {
  const R = window.READER || { pages: [] };
  const img = document.getElementById("page-img");
  const counter = document.getElementById("counter");
  const dirToggle = document.getElementById("dir-toggle");
  const total = R.pages.length;
  if (!img || !total) return;

  let dir = localStorage.getItem("mandom_dir") || R.direction || "rtl";
  let idx = 0;

  function preload(n) {
    if (n >= 0 && n < total) {
      const im = new Image();
      im.src = R.pages[n];
    }
  }

  function render() {
    img.src = R.pages[idx];
    counter.textContent = idx + 1 + " / " + total;
    preload(idx + 1);
    preload(idx - 1);
    window.scrollTo(0, 0);
  }

  // delta is in reading order: +1 = next page, -1 = previous.
  function go(delta) {
    const n = idx + delta;
    if (n < 0) {
      if (R.prevUrl) location.href = R.prevUrl;
      return;
    }
    if (n >= total) {
      if (R.nextUrl) location.href = R.nextUrl;
      return;
    }
    idx = n;
    render();
  }

  // In RTL, the left side advances the story; in LTR the right side does.
  function leftZone() { go(dir === "rtl" ? +1 : -1); }
  function rightZone() { go(dir === "rtl" ? -1 : +1); }

  document.getElementById("edge-left").addEventListener("click", leftZone);
  document.getElementById("edge-right").addEventListener("click", rightZone);
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") leftZone();
    else if (e.key === "ArrowRight") rightZone();
    else if (e.key === " ") { e.preventDefault(); go(+1); }
  });

  function updateLabel() { dirToggle.textContent = dir === "rtl" ? "← RTL" : "LTR →"; }
  dirToggle.addEventListener("click", () => {
    dir = dir === "rtl" ? "ltr" : "rtl";
    localStorage.setItem("mandom_dir", dir);
    updateLabel();
  });

  updateLabel();
  render();
})();
