/* "Ask about this feedback" (owner: followup). Progressive enhancement: without JavaScript every
   form posts normally and the page reloads at the thread; with it, questions are sent in place. */
(function () {
  "use strict";
  if (window.hscFollowupLoaded) return;
  window.hscFollowupLoaded = true;

  function post(form, extra) {
    var body = new URLSearchParams(new FormData(form));
    Object.keys(extra || {}).forEach(function (k) { body.set(k, extra[k]); });
    return fetch(form.action, {
      method: "POST", body: body, credentials: "same-origin",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "Unexpected reply from the app (" + r.status + ")." }; });
    });
  }

  function fragment(html) {
    var t = document.createElement("template");
    t.innerHTML = (html || "").trim();
    return t.content.firstElementChild;
  }

  function maths(el) { if (el && window.hscRenderMath) window.hscRenderMath(el); }

  function setStatus(panel, msg, warn) {
    var s = panel.querySelector("[data-fu-status]");
    if (!s) return;
    s.textContent = msg || "";
    s.hidden = !msg;
    s.classList.toggle("warn", !!warn);
  }

  function updateCount(panel, j) {
    if (!j || !j.max) return;
    var c = panel.querySelector("[data-fu-count]");
    if (c) c.textContent = j.used + " of " + j.max + " questions used";
    var form = panel.querySelector("[data-fu-form]"), limit = panel.querySelector("[data-fu-limit]");
    if (form) form.hidden = j.remaining <= 0;
    if (limit) limit.hidden = j.remaining > 0;
  }

  function busy(form, on) {
    Array.prototype.forEach.call(form.querySelectorAll("button, textarea"), function (b) { b.disabled = on; });
  }

  function pendingTurn(text) {
    var li = document.createElement("li");
    li.className = "fu-turn fu-pending";
    var q = document.createElement("div"); q.className = "fu-q";
    var who = document.createElement("span"); who.className = "fu-who"; who.textContent = "You asked";
    var p = document.createElement("p"); p.textContent = text;
    q.appendChild(who); q.appendChild(p);
    var a = document.createElement("div"); a.className = "fu-a fu-thinking small muted";
    a.textContent = "Thinking about your question… this can take up to a minute.";
    li.appendChild(q); li.appendChild(a);
    return li;
  }

  function ask(form, submitter) {
    var panel = form.closest("[data-fu-panel]");
    var list = panel.querySelector("[data-fu-thread]");
    var box = form.querySelector("textarea[name=question]");
    var chip = submitter && submitter.name === "chip" ? submitter.value : "";
    var text = chip ? submitter.textContent.trim() : box.value.trim();
    if (!text) { box.focus(); return; }
    setStatus(panel, "");
    var pending = pendingTurn(text);
    list.appendChild(pending);
    pending.scrollIntoView({ block: "nearest", behavior: "smooth" });
    var request = post(form, { chip: chip });  // read the form before its fields are disabled
    busy(form, true);
    request.then(function (j) {
      pending.remove();
      if (j.html) {
        var li = fragment(j.html);
        list.appendChild(li);
        maths(li);
        li.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      if (j.ok && !chip) box.value = "";
      if (j.status === "offline") {
        var ref = panel.querySelector("[data-fu-reference]");
        if (ref) { ref.open = true; maths(ref); }
        setStatus(panel, j.message || "");
      } else if (!j.ok && !j.html) {
        setStatus(panel, j.error || "Your question could not be sent.", true);
      }
      updateCount(panel, j);
    }).catch(function () {
      pending.remove();
      setStatus(panel, "Could not reach HSC Companion. Your question is still in the box — try again.", true);
    }).then(function () { busy(form, false); });
  }

  function action(form) {
    var panel = form.closest("[data-fu-panel]");
    var turn = form.closest(".fu-turn");
    var request = post(form, {});
    busy(form, true);
    request.then(function (j) {
      if (j.html && turn) {
        var li = fragment(j.html);
        turn.replaceWith(li);
        maths(li);
      } else if (!j.ok) {
        busy(form, false);
        if (panel) setStatus(panel, j.error || "That did not work — try again.", true);
      }
      if (panel) updateCount(panel, j);
    }).catch(function () {
      busy(form, false);
      if (panel) setStatus(panel, "Could not reach HSC Companion — try again.", true);
    });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement) || !window.fetch) return;
    if (form.matches("[data-fu-form]")) { e.preventDefault(); ask(form, e.submitter); }
    else if (form.matches("[data-fu-action]") && form.closest("[data-fu-panel]")) { e.preventDefault(); action(form); }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey)) return;
    var box = e.target.closest && e.target.closest("[data-fu-form] textarea");
    if (!box) return;
    e.preventDefault();
    var form = box.form;
    if (form.requestSubmit) form.requestSubmit(); else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
  });
})();
