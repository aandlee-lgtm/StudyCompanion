/* Maths answer live preview (owner: maths). */
(function () {
  "use strict";
  var post = function (u, d) { return window.hscPost(u, d); };
  var flash = function (m) { return window.hscFlash(m); };
  var renderMath = function (r) { return window.hscRenderMath(r); };
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("answer-form");
    if (!form) return;
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
})();
