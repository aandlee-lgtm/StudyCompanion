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

/* Guided self-marking: the mark updates as the student ticks (same rule as the server:
   whole marks from the share of items ticked, then the deterministic cap). */
(function () {
  "use strict";
  function derive(marks, n, ticked, cap) {
    if (n <= 0) return { raw: 0, final: 0 };
    var raw = Math.max(0, Math.min(marks, Math.floor(marks * ticked / n + 0.5)));
    var fin = (cap === "" || cap === null || isNaN(cap)) ? raw : Math.min(raw, cap);
    return { raw: raw, final: fin };
  }
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-guided]").forEach(function (form) {
      var marks = parseInt(form.dataset.marks || "0", 10);
      var n = parseInt(form.dataset.items || "0", 10);
      var cap = form.dataset.cap === "" ? "" : parseInt(form.dataset.cap, 10);
      var out = form.querySelector("[data-live-mark]");
      var note = form.querySelector("[data-live-note]");
      function update() {
        var t = form.querySelectorAll("input[name=tick]:checked").length;
        var d = derive(marks, n, t, cap);
        if (out) out.textContent = d.final;
        if (note) note.textContent = t + " of " + n + " ticked" + (d.final < d.raw ? " · capped from " + d.raw + " by the checks" : "");
      }
      form.addEventListener("change", update);
      update();
    });
  });
})();
