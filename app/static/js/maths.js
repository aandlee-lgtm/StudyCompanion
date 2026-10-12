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

// Photos of handwritten working (upload, remove, and ask Claude to read the final answer).
(function () {
  const box = document.querySelector('[data-photos]');
  if (!box) return;
  const qid = box.dataset.qid, sq = box.dataset.sq;
  const thumbs = box.querySelector('[data-photo-thumbs]');
  const status = box.querySelector('[data-photo-status]');
  const readBtn = box.querySelector('[data-photo-read]');
  const reading = box.querySelector('[data-photo-reading]');
  const say = (t) => { status.textContent = t || ''; };
  function render(data) {
    thumbs.innerHTML = '';
    (data.photos || []).forEach((p) => {
      const fig = document.createElement('figure');
      fig.className = 'photo-thumb';
      fig.innerHTML = `<a href="${p.url}" target="_blank"><img src="${p.url}" alt="Working, page ${p.page}"></a>` +
        `<figcaption>Page ${p.page} <button type="button" class="link small">Remove</button></figcaption>`;
      fig.querySelector('button').onclick = async () => {
        const r = await fetch(`/api/working-photos/${p.id}`, { method: 'DELETE' });
        render(await r.json());
      };
      thumbs.appendChild(fig);
    });
    readBtn.hidden = !(data.photos || []).length;
    if (data.errors && data.errors.length) say(data.errors.join(' ')); else if (data.photos) say(data.photos.length ? `${data.photos.length} page${data.photos.length > 1 ? 's' : ''} added` : '');
  }
  async function upload(files) {
    if (!files || !files.length) return;
    const fd = new FormData();
    fd.append('question_id', qid);
    if (sq) fd.append('sq_id', sq);
    [...files].forEach((f) => fd.append('files', f));
    say('Uploading…');
    try { render(await (await fetch('/api/working-photos', { method: 'POST', body: fd })).json()); }
    catch (e) { say('The photo could not be uploaded. Try again.'); }
  }
  box.querySelector('[data-photo-input]').addEventListener('change', (e) => { upload(e.target.files); e.target.value = ''; });
  box.addEventListener('dragover', (e) => { e.preventDefault(); box.classList.add('drag'); });
  box.addEventListener('dragleave', () => box.classList.remove('drag'));
  box.addEventListener('drop', (e) => { e.preventDefault(); box.classList.remove('drag'); upload(e.dataTransfer.files); });
  document.addEventListener('paste', (e) => {
    const files = [...(e.clipboardData || {}).files || []].filter((f) => f.type.startsWith('image/'));
    if (files.length) upload(files);
  });
  readBtn.addEventListener('click', async () => {
    const fd = new FormData();
    fd.append('question_id', qid);
    if (sq) fd.append('sq_id', sq);
    readBtn.disabled = true; say('Reading your handwriting… this can take a little while.');
    try {
      const r = await fetch('/api/working-photos/read', { method: 'POST', body: fd });
      const data = await r.json();
      if (!data.ok) { say(''); reading.hidden = false; reading.textContent = data.error; return; }
      const rd = data.reading;
      const ans = document.getElementById('ans');
      const parts = Object.entries(rd.part_answers || {});
      if (ans && parts.length) ans.value = parts.map(([k, v]) => `(${k}) ${v}`).join('\n');
      else if (ans && rd.final_answer) ans.value = rd.final_answer;
      if (ans) ans.dispatchEvent(new Event('input', { bubbles: true }));
      const work = document.getElementById('work');
      if (work && rd.working_text && !work.value.trim()) work.value = rd.working_text;
      reading.hidden = false;
      reading.textContent = (rd.legible ? 'Check what was read before you submit — fix anything that is wrong.' : 'The photo was hard to read — please check or type your answer.') +
        (rd.unclear && rd.unclear.length ? ' Unclear: ' + rd.unclear.join('; ') : '');
      say('');
    } catch (e) { say('The photo could not be read. Type your answer instead.'); }
    finally { readBtn.disabled = false; }
  });
  fetch(`/api/working-photos?question_id=${qid}${sq ? `&sq_id=${sq}` : ''}`).then((r) => r.json()).then(render).catch(() => {});
})();
