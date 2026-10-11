/* Question page: autosave, word count, per-question timer, split reading/writing layout and
   full-screen writing with the passage and question beside the answer (owner: english-logic). */
(function () {
  "use strict";
  var post = function (u, d) { return window.hscPost(u, d); };
  var flash = function (m) { return window.hscFlash(m); };
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("answer-form");
    if (!form) return;
    var area = form.querySelector("[data-autosave]");
    var saveUrl = form.dataset.saveUrl;
    var started = Date.now() - (parseInt(form.dataset.spent || "0", 10) * 1000);
    var timeField = form.querySelector("input[name=time_seconds]");
    var bar = form.querySelector(".en-toolbar");
    var low = bar ? parseInt(bar.dataset.suggestLow || "0", 10) : 0;
    var high = bar ? parseInt(bar.dataset.suggestHigh || "0", 10) : 0;
    var last = area ? area.value : "";
    function seconds() { return Math.round((Date.now() - started) / 1000); }
    function setSaved(msg) { $all("[data-save-state]").forEach(function (el) { el.textContent = msg; }); }
    function save(force) {
      if (!area || !saveUrl) return;
      var working = form.querySelector("textarea[name=working]");
      var text = area.value + (working ? "\n<<WORKING>>\n" + working.value : "");
      if (!force && text === last) return;
      last = text;
      setSaved("Saving…");
      post(saveUrl, { text: text, time_seconds: seconds() }).then(function (r) {
        if (r.ok) { var d = new Date(); setSaved("Saved " + d.getHours() + ":" + String(d.getMinutes()).padStart(2, "0")); flash("Saved"); }
        else setSaved("Not saved — check the app is running");
      }).catch(function () { setSaved("Not saved — check the app is running"); });
    }
    if (area && saveUrl) {
      setInterval(function () { save(false); }, 5000);
      area.addEventListener("blur", function () { save(false); });
      window.addEventListener("beforeunload", function () { save(false); });
      document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") save(false); });
    }
    function count() {
      if (!area) return;
      var n = (area.value.trim().match(/\S+/g) || []).length;
      $all("[data-word-count]").forEach(function (el) {
        el.textContent = n + " word" + (n === 1 ? "" : "s");
        el.classList.toggle("en-over", high > 0 && n > high * 1.5);
        el.classList.toggle("en-in", high > 0 && n >= low && n <= high);
      });
    }
    if (area) { area.addEventListener("input", count); count(); }
    setInterval(function () {
      var s = seconds();
      if (timeField) timeField.value = s;
      var t = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
      $all("[data-q-timer]").forEach(function (el) { el.textContent = t; });
    }, 1000);
    form.addEventListener("submit", function () { if (timeField) timeField.value = seconds(); });

    /* ---- split layout at desktop width: the passage beside the question and answer (english-14) ---- */
    var reading = document.getElementById("reading-pane");
    var card = form.closest(".card");
    if (reading && card && area && reading.nextElementSibling === card) {
      var split = document.createElement("div");
      split.className = "en-split";
      reading.parentNode.insertBefore(split, reading);
      split.appendChild(reading);
      split.appendChild(card);
    }

    /* ---- paragraph numbers on the passage ---- */
    $all("[data-para-numbers]").forEach(function (b) {
      var on = false;
      try { on = localStorage.getItem("hsc-para-numbers") === "1"; } catch (e) { on = false; }
      function apply() {
        $all(".en-reading, .en-full-text").forEach(function (r) { r.classList.toggle("en-numbered", on); });
        $all("[data-para-numbers]").forEach(function (x) { x.setAttribute("aria-pressed", on ? "true" : "false"); });
      }
      b.addEventListener("click", function () { on = !on; try { localStorage.setItem("hsc-para-numbers", on ? "1" : "0"); } catch (e) { /* ignore */ } apply(); });
      apply();
    });

    /* ---- full-screen writing: text | question + answer, with a sticky bar (english-14) ---- */
    var fs = document.getElementById("fullscreen");
    if (!fs || !area) return;
    var overlay = null, holder = null;
    function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
    function enter() {
      if (overlay) return;
      var qText = document.querySelector(".question-text");
      var marksEl = document.querySelector("h1 + .row strong");
      overlay = el("div", "en-full");
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-label", "Full-screen writing");
      var top = el("div", "en-full-bar");
      top.appendChild(el("span", "en-full-marks", marksEl ? marksEl.textContent : ""));
      var wc = el("span", "", '<span data-word-count></span>' + (high ? ' <span class="muted">(suggested ' + low + "–" + high + ")</span>" : ""));
      top.appendChild(wc);
      top.appendChild(el("span", "", 'Time <span data-q-timer>0:00</span>'));
      top.appendChild(el("span", "muted", '<span data-save-state>' + (saveUrl ? "Autosaves" : "") + "</span>"));
      var tabs = el("div", "en-full-tabs");
      var exit = el("button", "btn small", "Exit full screen (Esc)");
      exit.type = "button";
      exit.addEventListener("click", leave);
      top.appendChild(exit);
      overlay.appendChild(top);
      var body = el("div", "en-full-body");
      var left = el("div", "en-full-text en-full-pane");
      if (reading) {
        $all(".stimulus", reading).forEach(function (s) { left.appendChild(s.cloneNode(true)); });
      }
      var right = el("div", "en-full-write en-full-pane");
      var qBox = el("div", "en-full-question");
      if (qText) qBox.appendChild(qText.cloneNode(true));
      right.appendChild(qBox);
      holder = document.createComment("answer");
      area.parentNode.insertBefore(holder, area);
      area.setAttribute("form", form.id);  // keeps the answer in the form while it sits outside it
      right.appendChild(area);
      if (reading) body.appendChild(left); else body.classList.add("single");
      body.appendChild(right);
      // phone width: tabs instead of columns
      [["text", "Text", left], ["question", "Question", qBox], ["write", "Write", area]].forEach(function (t) {
        if (t[0] === "text" && !reading) return;
        var b = el("button", "btn small", t[1]); b.type = "button"; b.dataset.tab = t[0];
        b.addEventListener("click", function () { overlay.dataset.tab = t[0]; $all("[data-tab]", tabs).forEach(function (x) { x.classList.toggle("on", x === b); }); });
        tabs.appendChild(b);
      });
      overlay.dataset.tab = "write";
      overlay.appendChild(tabs);
      overlay.appendChild(body);
      document.body.appendChild(overlay);
      document.body.classList.add("en-full-open");
      $all("[data-tab]", tabs).forEach(function (x) { x.classList.toggle("on", x.dataset.tab === "write"); });
      if (document.querySelector(".en-reading.en-numbered")) left.classList.add("en-numbered");
      count();
      if (overlay.requestFullscreen) { overlay.requestFullscreen().catch(function () { /* the overlay still fills the window */ }); }
      area.focus();
    }
    function leave() {
      if (!overlay) return;
      holder.parentNode.insertBefore(area, holder);
      holder.parentNode.removeChild(holder);
      area.removeAttribute("form");
      var o = overlay; overlay = null;
      if (document.fullscreenElement && document.exitFullscreen) { document.exitFullscreen().catch(function () {}); }
      o.parentNode.removeChild(o);
      document.body.classList.remove("en-full-open");
      count();
      save(false);
      area.focus();
    }
    fs.addEventListener("click", function (e) { e.preventDefault(); enter(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && overlay && !document.fullscreenElement) leave(); });
    document.addEventListener("fullscreenchange", function () { if (!document.fullscreenElement && overlay) leave(); });
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
