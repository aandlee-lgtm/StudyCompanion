/* Core helpers shared by every page (owner: adaptive). The server (SQLite) is the source of truth. */
/* HSC Companion 2027 — small progressive enhancements. The server (SQLite) is the source of
   truth: drafts are autosaved there, never only in the browser. */
(function () {
  "use strict";

  function renderMath(root) {
    if (window.renderMathInElement) {
      window.renderMathInElement(root || document.body, {
        delimiters: [{ left: "\\[", right: "\\]", display: true }, { left: "\\(", right: "\\)", display: false }],
        throwOnError: false,
      });
    }
  }
  window.hscRenderMath = renderMath;
  document.addEventListener("DOMContentLoaded", function () { renderMath(); });

  function flash(msg) {
    var el = document.getElementById("flash");
    if (!el) return;
    el.textContent = msg; el.classList.add("show");
    clearTimeout(el._t); el._t = setTimeout(function () { el.classList.remove("show"); }, 1600);
  }
  window.hscFlash = flash;

  function post(url, data) {
    var body = new URLSearchParams();
    Object.keys(data || {}).forEach(function (k) { body.append(k, data[k]); });
    return fetch(url, { method: "POST", body: body, headers: { "X-Requested-With": "fetch" } });
  }
  window.hscPost = post;

  // ---- "Why did I lose the mark?" and feedback toggles ----
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-why]");
    if (b) {
      e.preventDefault();
      var out = document.getElementById(b.dataset.target);
      out.hidden = false; out.textContent = "Thinking about it…";
      post(b.dataset.why, {}).then(function (r) { return r.json(); }).then(function (j) {
        out.textContent = j.explanation; renderMath(out);
      }).catch(function () { out.textContent = "Could not load the explanation."; });
      return;
    }
    var tg = e.target.closest("[data-toggle]");
    if (tg) {
      e.preventDefault();
      var el = document.getElementById(tg.dataset.toggle);
      el.hidden = !el.hidden;
      if (tg.dataset.labelShow) tg.textContent = el.hidden ? tg.dataset.labelShow : tg.dataset.labelHide;
      renderMath(el);
    }
  });

})();
