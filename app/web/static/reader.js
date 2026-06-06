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

  // Which side / arrow advances to the NEXT page ("right" or "left").
  let advance = localStorage.getItem("mandom_advance") || R.advanceSide || "right";
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

  // The chosen side advances; the other goes back.
  function rightAction() { go(advance === "right" ? +1 : -1); }
  function leftAction() { go(advance === "right" ? -1 : +1); }

  document.getElementById("edge-right").addEventListener("click", rightAction);
  document.getElementById("edge-left").addEventListener("click", leftAction);
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") rightAction();
    else if (e.key === "ArrowLeft") leftAction();
    else if (e.key === " ") { e.preventDefault(); go(+1); }
  });

  function updateLabel() { dirToggle.textContent = advance === "right" ? "next →" : "← next"; }
  dirToggle.addEventListener("click", () => {
    advance = advance === "right" ? "left" : "right";
    localStorage.setItem("mandom_advance", advance);
    updateLabel();
  });

  updateLabel();
  render();
})();
