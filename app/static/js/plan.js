/* Learning plan drag-and-drop (owner: adaptive). */
(function () {
  "use strict";
  var post = function (u, d) { return window.hscPost(u, d); };
  var flash = function (m) { return window.hscFlash(m); };
  var renderMath = function (r) { return window.hscRenderMath(r); };
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
