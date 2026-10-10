/* Maths answers: live preview aware of the answer type, and one box per part for multi-part
   questions (owner: maths). The composed answer is kept in the form's own field, so autosave and
   submission work unchanged; without JavaScript the plain field still works. */
(function () {
  "use strict";
  var post = function (u, d) { return window.hscPost(u, d); };

  function previewer(input, out) {
    var timer = null, seq = 0;
    function run() {
      var text = input.value;
      var mine = ++seq;
      if (!text.trim()) { out.textContent = ""; out.classList.remove("err"); return; }
      post("/api/math-preview", { text: text, kind: input.dataset.kind || "expr", "var": input.dataset.var || "x" })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (mine !== seq) return; // a newer keystroke has superseded this request
          if (j.ok && window.katex) {
            out.classList.remove("err");
            try { katex.render(j.latex, out, { throwOnError: false }); } catch (e) { out.textContent = j.latex; }
          } else { out.textContent = j.message || ""; out.classList.toggle("err", !!j.message); }
        })
        .catch(function () { /* preview is optional */ });
    }
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 300); });
    if (input.value.trim()) run();
  }

  function splitParts(text, labels) {
    var out = {}, re = /^\s*\(\s*([a-h])\s*\)\s*(.*)$/i;
    (text || "").split(/\n/).forEach(function (line) {
      var m = line.match(re);
      if (m && labels.indexOf(m[1].toLowerCase()) >= 0 && out[m[1].toLowerCase()] === undefined) out[m[1].toLowerCase()] = m[2].trim();
    });
    return out;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("answer-form");
    if (!form) return;
    var single = form.querySelector("input[data-math-preview]");
    var pv = document.getElementById("math-preview");
    if (single && pv) previewer(single, pv);

    var box = form.querySelector("[data-maths-parts]");
    if (!box) return;
    var raw = box.querySelector("textarea[name=answer]");
    var inputs = Array.prototype.slice.call(box.querySelectorAll("[data-part-input]"));
    var labels = inputs.map(function (i) { return i.dataset.partInput; });
    var have = splitParts(raw.value, labels);
    function compose() {
      raw.value = inputs.map(function (i) { return "(" + i.dataset.partInput + ") " + i.value.replace(/\n/g, " "); }).join("\n");
    }
    inputs.forEach(function (i) {
      i.value = have[i.dataset.partInput] || "";
      i.closest(".maths-part").hidden = false;
      i.addEventListener("input", compose);
      var out = box.querySelector('[data-preview-for="' + i.dataset.partInput + '"]');
      if (out) previewer(i, out);
    });
    box.classList.add("enhanced");
    compose();
    form.addEventListener("submit", compose);
  });
})();
