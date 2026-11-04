// Modda frontend: state machine, rendering, margin notes, connecting curves, article drawer.
// Talks to FastAPI POST {API}/ask. With no server (or opened as a file) it falls back to mock-data.js.

(() => {
  const API = (window.MODDA_API ?? "").replace(/\/$/, "");
  const API_EXPLICIT = window.MODDA_API !== undefined;
  const params = new URLSearchParams(location.search);
  const FORCE_ERROR = params.get("demo") === "error";
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  const body = document.body;
  const form = $("#ask-form"), input = $("#question"), askBtn = $("#ask-btn");
  const form2 = $("#ask-again"), input2 = $("#question-2");
  const examples = $("#examples"), demoNote = $("#demo-note");
  const progress = $("#progress"), result = $("#result");
  const grid = result.querySelector(".result-grid");
  const answerQ = $("#answer-q"), answerBody = $("#answer-body"), answerFoot = $("#answer-foot");
  const notes = $("#notes"), links = $("#links");
  const statusText = $("#status-text");
  const drawer = $("#drawer"), backdrop = $("#drawer-backdrop");

  const outcome = el("div", "unknown");           // "I don't know" and error panels
  outcome.hidden = true;
  result.prepend(outcome);

  let useMock = location.protocol === "file:";
  let current = null;            // last response
  let lastQuestion = "";
  let timers = [];
  let activeIdx = -1;

  // ------------------------------------------------------------ helpers
  const MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"];
  function uzDate(iso) {
    const [y, m, d] = (iso || "").split("-").map(Number);
    return y ? `${y}-yil ${d}-${MONTHS[m - 1]}` : "";
  }
  function docLine(s) {
    const date = s.adoption_date ? s.adoption_date.split("-").reverse().join(".") : "";
    const type = s.title && s.doc_type && s.title.includes(s.doc_type) ? "" : s.doc_type;   // avoid "Qonun, Qonun"
    return [type, s.doc_number, date].filter(Boolean).join(", ");
  }
  const later = (fn, ms) => timers.push(setTimeout(fn, REDUCED ? 0 : ms));
  const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };

  function setState(s) {
    body.dataset.state = s;
    progress.hidden = s !== "loading";
    result.hidden = !["result", "unknown", "error"].includes(s);
    grid.hidden = s !== "result";
    outcome.hidden = !["unknown", "error"].includes(s);
  }

  function autoGrow(t) { t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 180) + "px"; }
  for (const t of [input, input2]) {
    t.addEventListener("input", () => autoGrow(t));
    t.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); t.form.requestSubmit(); }
    });
  }

  // ------------------------------------------------------------ API
  async function checkHealth() {
    if (useMock) return setStatus(false);
    try {
      const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2500) });
      if (!r.ok) throw new Error(r.status);
      const h = await r.json().catch(() => ({}));
      statusText.textContent = h.checked_at ? `Baza ${uzDate(h.checked_at)} holatida` : "Server ulangan";
    } catch {
      if (!API_EXPLICIT) useMock = true;
      setStatus(false);
    }
  }
  function setStatus(online) {
    if (!online) { statusText.textContent = "Namuna rejimi"; demoNote.hidden = false; }
  }

  async function ask(question) {
    if (FORCE_ERROR) { await new Promise((r) => setTimeout(r, 1500)); throw new Error("demo"); }
    if (useMock) return mockAsk(question);
    try {
      const r = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: AbortSignal.timeout(60000),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (err) {
      if (API_EXPLICIT) throw err;      // a configured server failed: show the error state
      useMock = true;                   // no server next to the page: switch to sample data
      setStatus(false);
      return mockAsk(question);
    }
  }

  // ------------------------------------------------------------ flow
  async function submit(question) {
    question = question.trim();
    if (!question) return;
    lastQuestion = question;
    closeDrawer();
    clearTimers();
    setState("loading");
    askBtn.disabled = true;
    window.scrollTo({ top: 0, behavior: REDUCED ? "auto" : "smooth" });

    const steps = [...progress.querySelectorAll("li")];
    steps.forEach((li) => li.classList.remove("on", "done"));
    const mark = (i) => steps.forEach((li, j) => { li.classList.toggle("done", j < i); li.classList.toggle("on", j === i); });
    mark(0);
    later(() => mark(1), 900);
    later(() => mark(2), 1800);

    try {
      const data = await ask(question);
      clearTimers();
      mark(3);
      current = data;
      if (data.unknown || !data.answer?.length) renderUnknown(question);
      else renderAnswer(question, data);
    } catch (err) {
      clearTimers();
      renderError(err);
    } finally {
      askBtn.disabled = false;
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); submit(input.value); });
  form2.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input2.value;
    input2.value = ""; autoGrow(input2);
    submit(q);
  });

  for (const ex of EXAMPLES) {
    const li = el("li");
    const b = el("button");
    b.type = "button";
    b.append(el("span", "ex-q", ex.text), el("span", "ex-h", ex.hint));
    b.addEventListener("click", () => { input.value = ex.text; submit(ex.text); });
    li.append(b);
    examples.append(li);
  }

  // ------------------------------------------------------------ answer
  function renderAnswer(question, data) {
    setState("result");
    answerQ.textContent = question;
    answerBody.replaceChildren();
    notes.replaceChildren();
    links.replaceChildren();
    answerFoot.replaceChildren();
    activeIdx = -1;

    // number sources by first appearance
    const order = [];
    for (const s of data.answer) for (const id of s.chunk_ids) if (!order.includes(id) && data.sources[id]) order.push(id);
    const num = (id) => order.indexOf(id) + 1;

    const noteEls = {};
    for (const id of order) {
      noteEls[id] = buildNote(id, num(id), data.sources[id], data.answer.find((s) => s.chunk_ids.includes(id))?.quote, false);
      notes.append(noteEls[id]);
    }

    const sentEls = data.answer.map((s, i) => {
      const p = el("p", "sent");
      p.tabIndex = 0;
      p.dataset.i = i;
      p.append(document.createTextNode(s.text));
      for (const id of s.chunk_ids) {
        if (!data.sources[id]) continue;
        const c = el("button", "cite", String(num(id)));
        c.type = "button";
        const src = data.sources[id];
        c.setAttribute("aria-label", `Manba ${num(id)}: ${src.article_no}-modda, ${src.article_title}. Toʻliq matnni ochish`);
        c.addEventListener("click", (e) => { e.stopPropagation(); openDrawer(id, s.quote, c); });
        p.append(c);
      }
      p.addEventListener("mouseenter", () => activate(i));
      p.addEventListener("focus", () => activate(i));
      p.addEventListener("click", () => activate(i));
      answerBody.append(p);
      // mobile: the source appears inline under the first sentence that cites it
      for (const id of s.chunk_ids) {
        if (data.sources[id] && data.answer.findIndex((x) => x.chunk_ids.includes(id)) === i) {
          answerBody.append(buildNote(id, num(id), data.sources[id], s.quote, true));
        }
      }
      return p;
    });

    // foot
    const stale = order.some((id) => data.sources[id].stale);
    answerFoot.append(el("span", "verified-line", `${data.answer.length} ta gapning har biri manba matni bilan solishtirildi`));
    if (stale) answerFoot.append(warnBox("Manbalardan biriga yaqinda oʻzgartirish kiritilgan boʻlishi mumkin — Lex.uz’da tekshiring."));
    if (data.checked_at) answerFoot.append(el("span", null, `Lex.uz bilan ${uzDate(data.checked_at)}da solishtirilgan.`));

    layoutNotes();

    // reveal sentences one by one, then stamp the citations
    sentEls.forEach((p, i) => {
      later(() => {
        p.classList.add("in");
        later(() => {
          p.classList.add("verified");
          p.querySelectorAll(".cite").forEach((c) => c.classList.add("stamp"));
          for (const id of data.answer[i].chunk_ids) noteEls[id]?.classList.add("in");
          if (i === 0) activate(0);
        }, 350);
      }, 250 + i * 420);
    });
  }

  function warnBox(text) {
    const w = el("div", "warn");
    w.setAttribute("role", "note");
    w.append(el("span", null, text));
    return w;
  }

  function buildNote(id, n, src, quote, inline) {
    const box = el("div", inline ? "note inline" : "note");
    box.dataset.id = id;
    const head = el("div", "note-head");
    head.append(el("span", "note-num", String(n)), el("span", "note-title", `${src.article_no}-modda. ${src.article_title}`));
    box.append(head, el("p", "note-doc", `${src.title}, ${docLine(src)}`));
    if (quote) box.append(el("blockquote", "note-quote", `«${quote}»`));
    if (src.amendment_note) box.append(el("p", "note-doc", src.amendment_note));
    if (src.stale) box.append(warnBox("Bu hujjatga yaqinda oʻzgartirish kiritilgan boʻlishi mumkin — Lex.uz’da tekshiring."));
    const actions = el("div", "note-actions");
    const open = el("button", "link-btn", "Toʻliq moddani koʻrish");
    open.type = "button";
    open.addEventListener("click", () => openDrawer(id, quote, open));
    const lex = el("a", null, "Lex.uz’da ochish");
    lex.href = src.url; lex.target = "_blank"; lex.rel = "noopener";
    actions.append(open, lex);
    box.append(actions);
    return box;
  }

  // place each note level with the first sentence that cites it; push down on collision
  function layoutNotes() {
    if (!current || body.dataset.state !== "result") return;
    const g = grid.getBoundingClientRect();
    let floor = 0;
    for (const note of notes.querySelectorAll(".note")) {
      const i = current.answer.findIndex((s) => s.chunk_ids.includes(note.dataset.id));
      const sent = answerBody.querySelector(`.sent[data-i="${i}"]`);
      const nRect = notes.getBoundingClientRect();
      const want = sent ? sent.getBoundingClientRect().top - nRect.top : 0;
      const top = Math.max(want, floor);
      note.style.top = `${top}px`;
      floor = top + note.offsetHeight + 16;
    }
    notes.style.height = `${floor}px`;
    links.setAttribute("viewBox", `0 0 ${g.width} ${g.height}`);
    if (activeIdx >= 0) drawLink(activeIdx, false);
  }

  function activate(i) {
    if (!current || i === activeIdx) return;
    activeIdx = i;
    answerBody.querySelectorAll(".sent").forEach((p) => p.classList.toggle("active", +p.dataset.i === i));
    const ids = current.answer[i].chunk_ids;
    notes.querySelectorAll(".note").forEach((n) => n.classList.toggle("active", ids.includes(n.dataset.id)));
    drawLink(i, true);
  }

  // cubic Bézier from the end of the sentence's first line to the note's heading
  function drawLink(i, animate) {
    links.replaceChildren();
    if (getComputedStyle(notes).display === "none") return;
    const g = grid.getBoundingClientRect();
    const sent = answerBody.querySelector(`.sent[data-i="${i}"]`);
    if (!sent) return;
    const sr = sent.getBoundingClientRect();
    const ns = "http://www.w3.org/2000/svg";
    for (const id of current.answer[i].chunk_ids) {
      const note = notes.querySelector(`.note[data-id="${CSS.escape(id)}"]`);
      if (!note) continue;
      const nr = note.getBoundingClientRect();
      const x1 = sr.right - g.left + 6, y1 = sr.top - g.top + 20;
      const x2 = nr.left - g.left - 6, y2 = nr.top - g.top + 26;
      const dx = (x2 - x1) * .5;
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`);
      const dot1 = document.createElementNS(ns, "circle");
      dot1.setAttribute("cx", x1); dot1.setAttribute("cy", y1); dot1.setAttribute("r", 3);
      const dot2 = document.createElementNS(ns, "circle");
      dot2.setAttribute("cx", x2); dot2.setAttribute("cy", y2); dot2.setAttribute("r", 3);
      links.append(path, dot1, dot2);
      const len = Math.ceil(path.getTotalLength());
      path.style.setProperty("--len", len);
      if (!animate) path.style.animation = "none", path.style.strokeDashoffset = 0;
    }
  }

  let raf = 0;
  addEventListener("resize", () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(layoutNotes); });
  if (document.fonts) document.fonts.ready.then(layoutNotes);
  // notes and sentences slide into place; redraw the curve once they stop moving
  grid.addEventListener("transitionend", (e) => {
    if (activeIdx >= 0 && (e.target.classList.contains("note") || e.target.classList.contains("sent"))) drawLink(activeIdx, false);
  });
  if (window.ResizeObserver) new ResizeObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(layoutNotes); }).observe(answerBody);

  // ------------------------------------------------------------ unknown / error
  function renderUnknown(question) {
    setState("unknown");
    outcome.replaceChildren(
      el("h2", null, "Bu savolga Lex.uz maʼlumotlari asosida ishonchli javob topilmadi."),
      el("p", "q-echo", `«${question}»`),
      el("p", null, "Taxminiy javob bermaslik uchun tizim toʻxtadi. Savolni aniqroq yozib koʻring: hujjat turini, sohani yoki kimga tegishli ekanini qoʻshing."),
    );
    const p = el("p");
    const a = el("a", null, "Lex.uz’da qidirish");
    a.href = `https://lex.uz/search/all?query=${encodeURIComponent(question)}`;
    a.target = "_blank"; a.rel = "noopener";
    p.append(a);
    outcome.append(p);
    outcome.querySelector("h2").tabIndex = -1;
    outcome.querySelector("h2").focus({ preventScroll: true });
  }

  function renderError(err) {
    setState("error");
    outcome.replaceChildren(
      el("h2", null, "Javob olishning imkoni boʻlmadi"),
      el("p", null, "Server javob bermadi yoki aloqa uzildi. Savolingiz saqlangan — qayta urinib koʻring."),
    );
    const retry = el("button", "ask-btn", "Qayta urinish");
    retry.type = "button";
    retry.addEventListener("click", () => submit(lastQuestion));
    outcome.append(retry);
    console.warn("Modda:", err);
    retry.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------ drawer
  let opener = null;
  function openDrawer(id, quote, from) {
    const src = current?.sources[id];
    if (!src) return;
    opener = from || document.activeElement;
    $("#drawer-doc").textContent = `${src.title}, ${docLine(src)}`;
    $("#drawer-title").textContent = `${src.article_no}-modda. ${src.article_title}`;
    const bodyEl = $("#drawer-body");
    bodyEl.replaceChildren();
    let marked = null;
    for (const para of src.text.split("\n")) {
      const p = el("p");
      const at = quote ? para.toLowerCase().indexOf(quote.toLowerCase()) : -1;
      if (at >= 0 && !marked) {
        marked = el("mark", null, para.slice(at, at + quote.length));
        p.append(para.slice(0, at), marked, para.slice(at + quote.length));
      } else p.textContent = para;
      bodyEl.append(p);
    }
    const foot = $("#drawer-foot");
    foot.replaceChildren();
    if (src.amendment_note) foot.append(el("span", null, src.amendment_note));
    if (src.stale) foot.append(warnBox("Bu hujjatga yaqinda oʻzgartirish kiritilgan boʻlishi mumkin — Lex.uz’da tekshiring."));
    foot.append(el("span", null, "Bu matn Lex.uz’dan olingan nusxa. Rasmiy matn — Lex.uz’dagi hujjat."));
    const a = el("a", null, "Hujjatni Lex.uz’da ochish");
    a.href = src.url; a.target = "_blank"; a.rel = "noopener";
    foot.append(a);

    drawer.hidden = false; backdrop.hidden = false;
    document.documentElement.style.overflow = "hidden";
    $("#drawer-close").focus();
    if (marked) requestAnimationFrame(() => marked.scrollIntoView({ block: "center", behavior: REDUCED ? "auto" : "smooth" }));
  }
  function closeDrawer() {
    if (drawer.hidden) return;
    drawer.hidden = true; backdrop.hidden = true;
    document.documentElement.style.overflow = "";
    opener?.focus?.({ preventScroll: true });
  }
  $("#drawer-close").addEventListener("click", closeDrawer);
  backdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (drawer.hidden) return;
    if (e.key === "Escape") closeDrawer();
    if (e.key === "Tab") {         // keep focus inside the dialog
      const f = [...drawer.querySelectorAll("button, a[href]")];
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  setState("empty");
  checkHealth().then(() => {
    if (params.get("q")) { input.value = params.get("q"); submit(input.value); }
  });
})();
