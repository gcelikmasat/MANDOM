// Browse tab active-state toggle.
function setActive(btn) {
  btn.parentElement.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
  btn.classList.add("is-active");
}

// Shuffling wallpaper: a faint full-screen backdrop PLUS a crisp, credited card
// on the side. Drop images into wallpapers/ and (optionally) map artist handles
// in wallpapers/credits.json. Falls back to the CSS gradient if empty.
(function () {
  const bg = document.getElementById("bg");
  const side = document.getElementById("wallpaper-side");
  const sideImg = side ? side.querySelector("img") : null;
  const credit = side ? side.querySelector(".wp-credit") : null;
  let shots = [];
  let i = 0;

  function show(item) {
    if (bg) {
      const pre = new Image();
      pre.onload = () => {
        bg.style.opacity = "0";
        setTimeout(() => {
          bg.style.backgroundImage = `url("${item.url}")`;
          bg.style.opacity = "1";
        }, 350);
      };
      pre.src = item.url;
    }
    if (sideImg) sideImg.src = item.url;
    if (credit) {
      if (item.handle) {
        credit.innerHTML =
          `art by <a href="${item.credit_url}" target="_blank" rel="noopener">${item.handle}</a>`;
        credit.style.display = "";
      } else {
        credit.textContent = "";
        credit.style.display = "none";
      }
    }
    if (side) side.classList.add("show");
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
      // Tolerate the old string-only format too.
      shots = list
        .map((x) => (typeof x === "string" ? { url: x, handle: null, credit_url: null } : x))
        .sort(() => Math.random() - 0.5);
      show(shots[0]);
      setInterval(next, 30000); // rotate every 30s
    })
    .catch(() => {});
})();
