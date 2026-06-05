// Browse tab active-state toggle.
function setActive(btn) {
  btn.parentElement.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
  btn.classList.add("is-active");
}

// Shuffling wallpaper background. Drop images into the project's wallpapers/
// folder and they rotate here. Falls back to the CSS gradient if empty.
(function () {
  const bg = document.getElementById("bg");
  if (!bg) return;
  let shots = [];
  let i = 0;

  function show(url) {
    const img = new Image();
    img.onload = () => {
      bg.style.opacity = "0";
      setTimeout(() => {
        bg.style.backgroundImage = `url("${url}")`;
        bg.style.opacity = "1";
      }, 350);
    };
    img.src = url;
  }

  function next() {
    if (!shots.length) return;
    i = (i + 1) % shots.length;
    show(shots[i]);
  }

  fetch("/api/wallpapers")
    .then((r) => r.json())
    .then((list) => {
      if (!Array.isArray(list) || !list.length) return;
      // Shuffle once so each load starts somewhere different.
      shots = list.sort(() => Math.random() - 0.5);
      show(shots[0]);
      setInterval(next, 30000); // rotate every 30s
    })
    .catch(() => {});
})();
