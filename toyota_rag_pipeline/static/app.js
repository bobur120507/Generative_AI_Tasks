// Kitob RAG - frontend. Plain JavaScript, no build step.
// All text coming from files or the model is inserted with textContent (never innerHTML),
// so an uploaded book cannot inject HTML/JS into the page.

const $ = (sel) => document.querySelector(sel);
const STATUS_LABEL = {
  queued: "navbatda", extracting: "matn ajratilmoqda", embedding: "vektorga aylantirilmoqda",
  ready: "tayyor", error: "xato",
};
const TYPE_ICON = { pdf: "📕", docx: "📘", md: "📝", txt: "📄" };
const excluded = new Set();          // book ids the user unticked
let books = [];
let pollTimer = null;

// ------------------------------------------------------------------ helpers
async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Server xatosi (${res.status})`);
  return data;
}
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  for (const c of children) if (c != null) node.append(c);
  return node;
}
const fmtMB = (b) => b < 1024 * 1024 ? Math.max(1, Math.round(b / 1024)) + " KB" : (b / 1024 / 1024).toFixed(1) + " MB";
const fmtNum = (n) => n.toLocaleString("uz-UZ");

// ------------------------------------------------------------------ status bar
async function loadStatus() {
  try {
    const s = await api("/api/status");
    const box = $("#status");
    box.className = "status " + (s.api_key ? "ok" : "bad");
    box.textContent = s.api_key
      ? `● ${s.chat_models[0]} · ${s.books_ready} kitob · ${fmtNum(s.chunks)} bo‘lak`
      : "● OPENROUTER_API_KEY o‘rnatilmagan (.env)";
  } catch { /* server not reachable - ignore */ }
}

// ------------------------------------------------------------------ library
async function loadBooks() {
  try {
    books = (await api("/api/books")).books;
  } catch (e) {
    return;
  }
  renderBooks();
  const busy = books.some((b) => ["queued", "extracting", "embedding"].includes(b.status));
  clearTimeout(pollTimer);
  if (busy) pollTimer = setTimeout(loadBooks, 1500);   // poll only while something is processing
  loadStatus();
}

function renderBooks() {
  const list = $("#book-list");
  list.replaceChildren();
  $("#library-empty").hidden = books.length > 0;
  $("#library-count").textContent = books.length ? `${books.length} ta` : "";

  for (const b of books) {
    const node = $("#book-tpl").content.firstElementChild.cloneNode(true);
    const ready = b.status === "ready";
    const busy = !ready && b.status !== "error";
    const check = node.querySelector("input");
    check.checked = ready && !excluded.has(b.id);
    check.disabled = !ready;
    check.onchange = () => { check.checked ? excluded.delete(b.id) : excluded.add(b.id); updateScope(); };

    node.querySelector(".book-title").textContent = `${TYPE_ICON[b.file_type] || "📄"} ${b.title || b.filename}`;
    const badge = el("span", { className: "badge " + (ready ? "ready" : busy ? "busy" : "error"),
      textContent: STATUS_LABEL[b.status] + (busy && b.progress ? ` ${b.progress}%` : "") });
    const meta = node.querySelector(".book-meta");
    meta.append(badge, " ", b.filename + " · " + fmtMB(b.size_bytes));
    if (ready) meta.append(el("br"), `${fmtNum(b.chapters)} bo‘lim · ${fmtNum(b.chunks)} bo‘lak · ${b.requests} so‘rov`);

    const progress = node.querySelector(".progress");
    progress.hidden = !busy;
    progress.querySelector(".bar").style.width = (b.progress || 2) + "%";
    const err = node.querySelector(".book-error");
    err.hidden = !b.error;
    err.textContent = b.error || "";

    node.querySelector(".retry").hidden = b.status !== "error";
    node.querySelector(".retry").onclick = () => api(`/api/books/${b.id}/retry`, { method: "POST" }).then(loadBooks);
    node.querySelector(".info").onclick = () => showDetails(b.id);
    node.querySelector(".delete").onclick = async () => {
      if (!confirm(`“${b.title || b.filename}” kutubxonadan o‘chirilsinmi?`)) return;
      await api(`/api/books/${b.id}`, { method: "DELETE" });
      loadBooks();
    };
    list.append(node);
  }
  updateScope();
}

function selectedIds() {
  return books.filter((b) => b.status === "ready" && !excluded.has(b.id)).map((b) => b.id);
}
function updateScope() {
  const ready = books.filter((b) => b.status === "ready").length;
  const sel = selectedIds().length;
  $("#scope-hint").textContent = ready
    ? `Qidiruv: ${sel} / ${ready} ta tayyor kitob ichida.`
    : "Savol berish uchun kamida bitta kitob tayyor bo‘lishi kerak.";
}

// ------------------------------------------------------------------ upload
async function upload(files) {
  if (!files.length) return;
  const msg = $("#upload-msg");
  const form = new FormData();
  for (const f of files) form.append("file", f);
  const title = $("#title-input").value.trim();
  if (title) form.append("title", title);
  msg.className = "msg";
  msg.textContent = `Yuklanmoqda: ${[...files].map((f) => f.name).join(", ")}…`;
  try {
    const res = await fetch("/api/books", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));
    const dup = (data.books || []).filter((b) => b.duplicate).length;
    const errs = (data.errors || []).map((e) => `${e.filename}: ${e.error}`);
    if (!res.ok && !errs.length) errs.push(data.error || `Server xatosi (${res.status})`);
    msg.className = "msg " + (errs.length ? "err" : "ok");
    msg.textContent = errs.length ? errs.join("\n")
      : dup ? "Bu kitob kutubxonada allaqachon bor." : "Qabul qilindi — qayta ishlanmoqda.";
    $("#title-input").value = "";
  } catch (e) {
    msg.className = "msg err";
    msg.textContent = e.message;
  }
  loadBooks();
}

const dz = $("#dropzone");
$("#file-input").onchange = (e) => { upload(e.target.files); e.target.value = ""; };
["dragenter", "dragover"].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach((t) => dz.addEventListener(t, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", (e) => upload(e.dataTransfer.files));

// ------------------------------------------------------------------ chat
function renderAnswer(text, sourcesBox) {
  // "[2]" -> clickable chip that opens the matching source; "**bold**" -> <b>
  const frag = document.createDocumentFragment();
  for (const part of text.split(/(\[\d+\]|\*\*[^*\n]+\*\*)/)) {
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite) {
      frag.append(el("button", { className: "cite", type: "button", textContent: cite[1],
        onclick: () => {
          const d = sourcesBox.querySelector(`[data-n="${cite[1]}"]`);
          if (!d) return;
          d.open = true;
          d.scrollIntoView({ behavior: "smooth", block: "nearest" });
          d.classList.remove("flash"); void d.offsetWidth; d.classList.add("flash");
        } }));
    } else if (/^\*\*.+\*\*$/.test(part)) {
      frag.append(el("b", { textContent: part.slice(2, -2) }));
    } else if (part) {
      frag.append(document.createTextNode(part));
    }
  }
  return frag;
}

function renderSources(sources) {
  const box = el("div", { className: "sources" });
  for (const s of sources) {
    const pct = Math.max(0, Math.min(1, s.score)) * 100;
    const scoreBar = el("span", { className: "score" }, el("i", {}, el("b", { style: `width:${pct}%` })), s.score.toFixed(2));
    const details = el("details", { className: "source" },
      el("summary", {}, el("span", { className: "cite", textContent: s.n }), el("span", { textContent: s.citation }), scoreBar),
      el("div", { className: "text", textContent: s.text }));
    details.dataset.n = s.n;
    if (s.url) details.append(el("a", { href: s.url, target: "_blank", rel: "noopener", textContent: "Manbani ochish ↗" }));
    box.append(details);
  }
  return box;
}

async function ask(question) {
  const box = $("#messages");
  $("#welcome")?.remove();
  box.append(el("div", { className: "bubble user", textContent: question }));
  const pending = el("div", { className: "bubble bot typing muted" });
  box.append(pending);
  box.scrollTop = box.scrollHeight;
  $("#ask-btn").disabled = true;
  try {
    const data = await api("/api/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, book_ids: selectedIds(), k: Number($("#k-select").value) }),
    });
    const sources = renderSources(data.sources);
    const bubble = el("div", { className: "bubble bot" }, renderAnswer(data.answer, sources));
    if (data.model) bubble.append(el("span", { className: "model-tag", textContent: `Model: ${data.model}` }));
    if (data.sources.length) bubble.append(sources);
    pending.replaceWith(bubble);
  } catch (e) {
    pending.replaceWith(el("div", { className: "bubble bot error", textContent: "⚠️ " + e.message }));
  } finally {
    $("#ask-btn").disabled = false;
    box.scrollTop = box.scrollHeight;
  }
}

$("#ask-form").onsubmit = (e) => {
  e.preventDefault();
  const q = $("#question").value.trim();
  if (!q || $("#ask-btn").disabled) return;
  $("#question").value = "";
  ask(q);
};
$("#question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#ask-form").requestSubmit(); }
});
document.querySelectorAll(".suggestions .chip").forEach((c) => { c.onclick = () => ask(c.textContent); });

// ------------------------------------------------------------------ details dialog
function histogram(lengths, maxLen) {
  // simple SVG bar chart of chunk lengths (bins of 50 characters)
  const binSize = 50, bins = Math.ceil(maxLen / binSize), counts = new Array(bins).fill(0);
  lengths.forEach((l) => counts[Math.min(bins - 1, Math.floor(l / binSize))]++);
  const W = 680, H = 170, pad = 28, top = Math.max(...counts, 1), bw = (W - pad) / bins;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H + 22}`);
  counts.forEach((c, i) => {
    const h = (c / top) * (H - 10);
    const r = document.createElementNS(ns, "rect");
    Object.entries({ x: pad + i * bw + 1, y: H - h, width: bw - 2, height: h, rx: 2 })
      .forEach(([k, v]) => r.setAttribute(k, v));
    r.style.fill = "var(--accent)";   // CSS variables work in style, not in SVG attributes
    const t = document.createElementNS(ns, "title");
    t.textContent = `${i * binSize}–${(i + 1) * binSize} belgi: ${c} ta bo‘lak`;
    r.append(t);
    svg.append(r);
  });
  [0, maxLen / 2, maxLen].forEach((v) => {
    const t = document.createElementNS(ns, "text");
    Object.entries({ x: pad + (v / maxLen) * (W - pad), y: H + 16, "font-size": 11, "text-anchor": "middle" })
      .forEach(([k, val]) => t.setAttribute(k, val));
    t.style.fill = "var(--muted)";
    t.textContent = `${v} belgi`;
    svg.append(t);
  });
  return svg;
}

async function showDetails(id) {
  const b = await api(`/api/books/${id}`);
  $("#d-title").textContent = b.title || b.filename;
  const stat = (v, label) => el("div", { className: "stat" }, el("b", { textContent: v }), el("span", { textContent: label }));
  $("#d-stats").replaceChildren(
    stat(b.file_type.toUpperCase(), "format"), stat(fmtMB(b.size_bytes), "hajm"),
    stat(fmtNum(b.characters), "belgi"), stat(fmtNum(b.chapters), "bo‘lim / sahifa"),
    stat(fmtNum(b.chunks), "bo‘lak"), stat(b.requests, "API so‘rov"),
  );
  const lengths = b.chunk_lengths || [];
  $("#d-hist").replaceChildren(lengths.length ? histogram(lengths, Math.max(800, ...lengths))
    : el("p", { className: "muted", textContent: "Hali ma’lumot yo‘q." }));
  $("#d-preview").replaceChildren(...(b.preview || []).map((p) =>
    el("div", { className: "preview" }, el("span", { className: "muted small", textContent: `${p.id} · ${p.chapter}` }), p.text)));
  $("#details").showModal();
}

// ------------------------------------------------------------------ start
loadBooks();
loadStatus();
