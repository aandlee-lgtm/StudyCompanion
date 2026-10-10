/* Session timer (owner: selection).
   Active time only (selection-13): on any page of a session the browser sends a heartbeat every
   30 s while the tab is visible and the student has been active in the last few minutes. The
   server credits at most 90 s between two signals, so a laptop left open overnight records
   nothing. Hiding the tab or leaving the page pauses the timer; after the idle limit the timer
   pauses itself and says so. */
(function () {
  "use strict";
  var BEAT_MS = 30000;

  function fmt(s) {
    s = Math.max(0, Math.round(s));
    return Math.floor(s / 3600) + ":" + String(Math.floor(s / 60) % 60).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }

  function post(url, data) {
    var body = new URLSearchParams();
    Object.keys(data || {}).forEach(function (k) { body.append(k, data[k]); });
    return fetch(url, { method: "POST", body: body, headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
  }

  function beacon(url, data) {
    var body = new URLSearchParams();
    Object.keys(data || {}).forEach(function (k) { body.append(k, data[k]); });
    if (navigator.sendBeacon) { navigator.sendBeacon(url, body); return; }
    post(url, data);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var m = location.pathname.match(/^\/session\/(\d+)(\/q\/\d+)?\/?$/);
    var el = document.getElementById("session-timer");
    var sid = el ? el.dataset.sid : (m ? m[1] : null);
    if (!sid) return;
    if (el && el.dataset.done === "1") { el.textContent = fmt(parseInt(el.dataset.elapsed || "0", 10)); return; }

    var idleMs = (el && parseInt(el.dataset.idle || "10", 10) || 10) * 60000;
    var base = el ? parseInt(el.dataset.elapsed || "0", 10) : 0;
    var running = el ? el.dataset.running === "1" : true;
    var t0 = Date.now(), lastInput = Date.now(), idlePaused = false;
    var countdown = el && el.dataset.countdown ? parseInt(el.dataset.countdown, 10) : null;
    var cdEl = document.getElementById("session-countdown");
    var noteEl = document.getElementById("pause-note");

    function current() { return base + (running ? (Date.now() - t0) / 1000 : 0); }
    function render() {
      if (el) el.textContent = fmt(current());
      if (cdEl && countdown !== null) {
        var left = countdown - current();
        cdEl.textContent = left > 0 ? "Exam conditions: " + fmt(left) + " left" : "Exam time is up — finish the question you are on.";
      }
    }
    function sync(j) {
      if (!j) return;
      base = j.elapsed || 0; running = !!j.running; t0 = Date.now();
      if (noteEl) { noteEl.textContent = j.note || ""; noteEl.hidden = !j.note; }
      render();
    }
    function beat() {
      if (document.hidden) return;
      if (Date.now() - lastInput > idleMs) {
        if (!idlePaused) {
          idlePaused = true;
          post("/session/" + sid + "/timer", { action: "pause", reason: "idle" }).then(function (r) { return r.json(); }).then(sync).catch(function () {});
        }
        return;
      }
      post("/session/" + sid + "/heartbeat", {}).then(function (r) { return r.json(); }).then(sync).catch(function () {});
    }
    function active() {
      lastInput = Date.now();
      if (idlePaused) { idlePaused = false; beat(); }
    }
    ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "input"].forEach(function (ev) {
      document.addEventListener(ev, active, { passive: true });
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { running = false; beacon("/session/" + sid + "/timer", { action: "pause", reason: "hidden" }); }
      else { lastInput = Date.now(); idlePaused = false; beat(); }
    });
    window.addEventListener("pagehide", function () { beacon("/session/" + sid + "/timer", { action: "pause", reason: "nav" }); });

    // the Pause / Start button works without a page reload
    var form = document.getElementById("timer-form");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var action = form.querySelector("input[name=action]");
        post(form.action, { action: action.value }).then(function (r) { return r.json(); }).then(function (j) {
          sync(j);
          action.value = j.running ? "pause" : "start";
          form.querySelector("button").textContent = j.running ? "Pause" : "Resume";
          idlePaused = !j.running;
        }).catch(function () { form.submit(); });
      });
    }
    render();
    setInterval(render, 1000);
    setInterval(beat, BEAT_MS);
    if (!document.hidden) beat();
  });
})();
