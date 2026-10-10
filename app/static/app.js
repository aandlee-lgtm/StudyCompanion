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

  // ---- question page: autosave, word count, per-question timer, fullscreen ----
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
    // maths live preview
    var mi = form.querySelector("input[data-math-preview]");
    var pv = document.getElementById("math-preview");
    if (mi && pv) {
      var t;
      mi.addEventListener("input", function () {
        clearTimeout(t);
        t = setTimeout(function () {
          post("/api/math-preview", { text: mi.value }).then(function (r) { return r.json(); }).then(function (j) {
            if (!mi.value.trim()) { pv.textContent = ""; return; }
            if (j.ok && window.katex) { try { katex.render(j.latex, pv, { throwOnError: false }); } catch (e) { pv.textContent = j.latex; } }
            else pv.textContent = j.message || "";
          });
        }, 300);
      });
    }
  });

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

  // ---- learning plan drag-and-drop reordering ----
  document.addEventListener("DOMContentLoaded", function () {
    var list = document.querySelector("[data-reorder-url]");
    if (!list) return;
    var dragging = null;
    list.addEventListener("dragstart", function (e) { dragging = e.target.closest(".plan-item"); if (dragging) dragging.classList.add("dragging"); });
    list.addEventListener("dragend", function () {
      if (!dragging) return;
      dragging.classList.remove("dragging"); dragging = null;
      var ids = Array.prototype.map.call(list.querySelectorAll(".plan-item"), function (el) { return el.dataset.id; });
      post(list.dataset.reorderUrl, { ids: ids.join(",") }).then(function (r) { if (r.ok) flash("Order saved"); });
    });
    list.addEventListener("dragover", function (e) {
      e.preventDefault();
      var after = Array.prototype.find.call(list.querySelectorAll(".plan-item:not(.dragging)"), function (el) {
        var box = el.getBoundingClientRect(); return e.clientY < box.top + box.height / 2;
      });
      if (!dragging) return;
      if (after) list.insertBefore(dragging, after); else list.appendChild(dragging);
    });
  });
})();
