/* Core helpers shared by every page (owner: adaptive). The server (SQLite) is the source of truth:
   drafts are autosaved there, never only in the browser. */
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

  // ---- record that a model response / full solution was opened (english-21) ----
  var modelPosted = {};
  function modelViewed(url) {
    if (!url || modelPosted[url]) return;
    modelPosted[url] = true;
    post(url, {}).catch(function () { modelPosted[url] = false; });
  }
  window.hscModelViewed = modelViewed;

  // ---- "Why did I lose the mark?" and feedback toggles ----
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-why]");
    if (b) {
      e.preventDefault();
      var out = document.getElementById(b.dataset.target);
      out.hidden = false; out.textContent = "Thinking about it…";
      post(b.dataset.why, {}).then(function (r) { return r.json(); }).then(function (j) {
        out.textContent = "";
        (j.paragraphs && j.paragraphs.length ? j.paragraphs : [j.explanation]).forEach(function (t) {
          var p = document.createElement("p"); p.textContent = t; out.appendChild(p);
        });
        renderMath(out);
      }).catch(function () { out.textContent = "Could not load the explanation."; });
      return;
    }
    var mv = e.target.closest("[data-model-viewed]");
    if (mv && mv.tagName !== "DETAILS") modelViewed(mv.dataset.modelViewed);
    var tg = e.target.closest("[data-toggle]");
    if (tg) {
      e.preventDefault();
      var el = document.getElementById(tg.dataset.toggle);
      el.hidden = !el.hidden;
      if (tg.dataset.labelShow) tg.textContent = el.hidden ? tg.dataset.labelShow : tg.dataset.labelHide;
      // convention used by the subject feedback partials: the model toggle targets "model-<attempt id>"
      var m = /^model-(\d+)$/.exec(tg.dataset.toggle);
      if (m && !el.hidden) modelViewed("/attempt/" + m[1] + "/model-viewed");
      renderMath(el);
    }
  });
  document.addEventListener("toggle", function (e) {
    var d = e.target;
    if (d.tagName === "DETAILS" && d.open && d.dataset && d.dataset.modelViewed) modelViewed(d.dataset.modelViewed);
  }, true);

  // ---- draft autosave for every answer form (session and practice), quiet status, beacon on leave ----
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("answer-form");
    if (!form || !form.dataset.saveUrl) return;
    var status = document.getElementById("save-status");
    var started = Date.now() - (parseInt(form.dataset.spent || "0", 10) * 1000);
    function seconds() { return Math.round((Date.now() - started) / 1000); }
    function current() {
      var ans = form.querySelector("textarea[name=answer]") || form.querySelector("input[name=answer]:not([type=radio])");
      var text = ans ? ans.value : "";
      if (!ans) { var r = form.querySelector("input[name=answer]:checked"); text = r ? r.value : ""; }
      var working = form.querySelector("textarea[name=working]");
      return text + (working && working.value ? "\n<<WORKING>>\n" + working.value : "");
    }
    var last = current(), failed = false, submitting = false;
    function hhmm() { var d = new Date(); return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }
    function setStatus(t) { if (status) status.textContent = t; }
    function save() {
      var text = current();
      if (submitting || (text === last && !failed)) return;
      post(form.dataset.saveUrl, { text: text, time_seconds: seconds() }).then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        last = text; failed = false; setStatus("Saved " + hhmm());
      }).catch(function () { failed = true; setStatus("Not saved — retrying"); });
    }
    function beacon() {
      var text = current();
      if (submitting || text === last || !navigator.sendBeacon) return;
      var body = new URLSearchParams(); body.append("text", text); body.append("time_seconds", String(seconds()));
      if (navigator.sendBeacon(form.dataset.saveUrl, body)) last = text;
    }
    setInterval(save, 6000);
    form.addEventListener("change", save);
    form.addEventListener("focusout", save);
    window.addEventListener("pagehide", beacon);
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") beacon(); });
    form.addEventListener("submit", function () { submitting = true; });
  });

  // ---- token-answer guard: a very short written answer looks like a skip (adaptive-23) ----
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("answer-form");
    var dlg = document.getElementById("short-answer-dialog");
    if (!form || !dlg || form.dataset.kind !== "written") return;
    var marks = parseInt(form.dataset.marks || "1", 10), confirmed = false;
    function words() { var a = form.querySelector("textarea[name=answer]"); return a ? (a.value.trim().match(/\S+/g) || []).length : 0; }
    form.addEventListener("submit", function (e) {
      if (confirmed || marks < 2) return;
      if (e.submitter && e.submitter.hasAttribute("data-skip")) return;
      var n = words();
      if (n === 0 || n >= 8) return;
      e.preventDefault(); e.stopImmediatePropagation();
      var c = dlg.querySelector("[data-short-count]");
      if (c) c.textContent = "Your answer has " + n + " word" + (n === 1 ? "" : "s") + " for a " + marks + "-mark question.";
      if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    }, true);
    dlg.addEventListener("click", function (e) {
      var b = e.target.closest("[data-short]");
      if (!b) return;
      var act = b.dataset.short;
      if (dlg.close) dlg.close(); else dlg.removeAttribute("open");
      if (act === "write") { var a = form.querySelector("textarea[name=answer]"); if (a) a.focus(); return; }
      confirmed = true;
      var tf = form.querySelector("input[name=time_seconds]");
      if (tf && !parseInt(tf.value || "0", 10)) tf.value = Math.round(parseInt(form.dataset.spent || "0", 10));
      if (act === "skip") form.action = form.dataset.skipUrl;
      form.submit();
    });
  });
})();
