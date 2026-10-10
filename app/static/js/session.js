/* Session timer (owner: selection). */
(function () {
  "use strict";
  var post = function (u, d) { return window.hscPost(u, d); };
  var flash = function (m) { return window.hscFlash(m); };
  var renderMath = function (r) { return window.hscRenderMath(r); };
  // ---- session timer (pause/resume persisted on server) ----
  document.addEventListener("DOMContentLoaded", function () {
    var el = document.getElementById("session-timer");
    if (!el) return;
    var base = parseInt(el.dataset.elapsed || "0", 10), running = el.dataset.running === "1", t0 = Date.now();
    function tick() {
      var s = base + (running ? Math.round((Date.now() - t0) / 1000) : 0);
      el.textContent = Math.floor(s / 3600) + ":" + String(Math.floor(s / 60) % 60).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
    }
    tick(); setInterval(tick, 1000);
  });

})();
