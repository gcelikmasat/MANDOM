// Browse tab active-state toggle.
function setActive(btn) {
  btn.parentElement.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
  btn.classList.add("is-active");
}

// Shuffling wallpaper banner in the header (visible at every width), with the
// artist credit. Drop images into wallpapers/ and (optionally) map handles in
// wallpapers/credits.json. The decorative ASCII art is relocated to the footer.
(function () {
  // Move the ASCII mascot out of the header and into the footer.
  const art = document.querySelector(".brand-art-wrap");
  const footer = document.getElementById("page-footer");
  if (art && footer) footer.appendChild(art);

  const banner = document.getElementById("topbar-bg");
  const credit = document.querySelector(".topbar-credit");
  if (!banner) return;
  let shots = [];
  let i = 0;

  function show(item) {
    const pre = new Image();
    pre.onload = () => {
      banner.style.opacity = "0";
      setTimeout(() => {
        banner.style.backgroundImage = `url("${item.url}")`;
        banner.style.opacity = "1";
      }, 300);
    };
    pre.src = item.url;
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
      shots = list
        .map((x) => (typeof x === "string" ? { url: x, handle: null, credit_url: null } : x))
        .sort(() => Math.random() - 0.5);
      show(shots[0]);
      setInterval(next, 30000); // rotate every 30s
    })
    .catch(() => {});
})();
