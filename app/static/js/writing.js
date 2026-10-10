/* Question page: autosave, word count, per-question timer, full-screen writing (owner: english-logic). */
(function () {
  "use strict";
  var post = function (u, d) { return window.hscPost(u, d); };
  var flash = function (m) { return window.hscFlash(m); };
  var renderMath = function (r) { return window.hscRenderMath(r); };
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("answer-form");
    if (!form) return;
    var area = form.querySelector("[data-autosave]");
    var saveUrl = form.dataset.saveUrl;
    var started = Date.now() - (parseInt(form.dataset.spent || "0", 10) * 1000);
    var timeField = form.querySelector("input[name=time_seconds]");
    var qTimer = document.getElementById("q-timer");
    var last = area ? area.value : "";
    function seconds() { return Math.round((Date.now() - started) / 1000); }
    function save(force) {
      if (!area || !saveUrl) return;
      var working = form.querySelector("textarea[name=working]");
      var text = area.value + (working ? "\n<<WORKING>>\n" + working.value : "");
      if (!force && text === last) return;
      last = text;
      post(saveUrl, { text: text, time_seconds: seconds() }).then(function (r) { if (r.ok) flash("Saved"); });
    }
    if (area && saveUrl) {
      setInterval(function () { save(false); }, 5000);
      area.addEventListener("blur", function () { save(false); });
      window.addEventListener("beforeunload", function () { save(false); });
    }
    var wc = document.getElementById("word-count");
    function count() { if (wc && area) { var n = (area.value.trim().match(/\S+/g) || []).length; wc.textContent = n + " words"; } }
    if (area) { area.addEventListener("input", count); count(); }
    setInterval(function () {
      var s = seconds();
      if (timeField) timeField.value = s;
      if (qTimer) qTimer.textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }, 1000);
    form.addEventListener("submit", function () { if (timeField) timeField.value = seconds(); });
    var fs = document.getElementById("fullscreen");
    if (fs && area) {
      fs.addEventListener("click", function (e) {
        e.preventDefault(); area.classList.toggle("full"); area.focus();
      });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") area.classList.remove("full"); });
    }
  });
})();
