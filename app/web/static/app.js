// Register the service worker so the app is installable (PWA). Only in a secure
// context (https or localhost) — avoids errors when accessed over plain http.
if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

// Browse tab active-state toggle.
function setActive(btn) {
  btn.parentElement.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
  btn.classList.add("is-active");
}

// Wallpapers: a faint full-screen backdrop plus two credited cards in the left
// and right gutters. They conveyor left -> right — the newest image enters on
// the left, last tick's left image moves to the right, e.g. (2,1)->(3,2)->(1,3).
(function () {
  const bg = document.getElementById("bg");
  const lImg = document.querySelector("#wp-left img");
  const rImg = document.querySelector("#wp-right img");
  const lCred = document.querySelector("#wp-left .wp-credit");
  const rCred = document.querySelector("#wp-right .wp-credit");

  let shots = [];
  let li = 0; // index shown on the LEFT (the newest)

  function setCredit(el, item) {
    if (!el) return;
    el.innerHTML = item.handle
      ? `art by <a href="${item.credit_url}" target="_blank" rel="noopener">${item.handle}</a>`
      : "";
  }

  function fillCard(img, cred, item) {
    if (!img) return;
    setCredit(cred, item);
    const pre = new Image();
    pre.onload = () => {
      img.src = item.url;
      img.classList.remove("in");
      void img.offsetWidth; // reflow so the slide-in animation replays
      img.classList.add("in");
    };
    pre.src = item.url;
  }

  function render() {
    const n = shots.length;
    const ri = (li - 1 + n) % n; // right = previous (older) image
    const leftItem = shots[li];
    const rightItem = shots[ri];
    if (bg) {
      bg.style.opacity = "0";
      setTimeout(() => {
        bg.style.backgroundImage = `url("${leftItem.url}")`;
        bg.style.opacity = "1";
      }, 300);
    }
    fillCard(lImg, lCred, leftItem);
    fillCard(rImg, rCred, rightItem);
  }

  function next() {
    if (shots.length) {
      li = (li + 1) % shots.length;
      render();
    }
  }

  fetch("/api/wallpapers")
    .then((r) => r.json())
    .then((list) => {
      if (!Array.isArray(list) || !list.length) return;
      shots = list
        .map((x) => (typeof x === "string" ? { url: x, handle: null, credit_url: null } : x))
        .sort(() => Math.random() - 0.5);
      li = shots.length > 1 ? 1 : 0; // first pair shows (shots[1], shots[0])
      render();
      setInterval(next, 8000); // conveyor every 8s
    })
    .catch(() => {});
})();
