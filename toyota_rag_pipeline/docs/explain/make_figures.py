#!/usr/bin/env python3
"""Draws the pictures used in I_EXPLAIN.md (saved next to this file).

Text figures (chunks, overlap, cleaning, prompt) are produced by running the
project's REAL code on the sample book and rendering the result as HTML -> PNG.
Vector figures (2-D arrows, cosine, search) are simplified sketches with
hand-placed points, because real embeddings have hundreds of dimensions.

  python docs/explain/make_figures.py        (needs matplotlib; playwright for the text figures)
"""

import html
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
sys.path.insert(0, str(ROOT))

from toyota_rag.chunking import RecursiveOverlapSplitter  # noqa: E402
from toyota_rag.cleaning import clean_text, remove_headers_footers  # noqa: E402
from toyota_rag.loaders import load_directory  # noqa: E402
from toyota_rag.rag import build_prompt  # noqa: E402
from toyota_rag.vectorstores import SearchResult  # noqa: E402

BLUE, RED, GREEN, ORANGE, PURPLE, GREY = "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#6b7280"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

CSS = """
body{margin:0;font-family:Inter,system-ui,sans-serif;background:#fff;color:#16181d;font-size:15px}
.wrap{padding:22px;width:1000px}
h2{font-size:18px;margin:0 0 14px} h3{font-size:14px;margin:16px 0 8px;color:#374151}
.row{display:flex;gap:16px}.col{flex:1}
.card{border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;margin-bottom:10px;line-height:1.5;background:#fafafa}
.lbl{font-size:12px;font-weight:700;color:#6b7280;margin-bottom:4px;display:flex;justify-content:space-between}
.ov{background:#fde68a;border-radius:3px;padding:0 2px}
.bad{border-color:#fca5a5;background:#fef2f2}.good{border-color:#86efac;background:#f0fdf4}
.note{font-size:13px;color:#374151;margin-top:6px}
.tag{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:999px;margin-left:6px}
.t-red{background:#fee2e2;color:#b91c1c}.t-green{background:#dcfce7;color:#15803d}
pre{white-space:pre-wrap;font-family:ui-monospace,Menlo,monospace;font-size:12.5px;margin:0;line-height:1.45}
.strike{background:#fee2e2;text-decoration:line-through;color:#b91c1c}
.p-ins{background:#dbeafe}.p-ctx{background:#fef3c7}.p-q{background:#dcfce7}
"""


def render_html(body: str, name: str):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"  skip {name} (pip install playwright to draw text figures)")
        return
    page_html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='wrap'>{body}</div></body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1044, "height": 400}, device_scale_factor=2)
        pg.set_content(page_html)
        pg.locator(".wrap").screenshot(path=str(OUT / name))
        b.close()
    print("  saved", name)


def esc(s):
    return html.escape(s)


# ------------------------------------------------------------------ real text from the sample book
DOCS = load_directory(ROOT / "tests" / "fixtures" / "sample_books", verbose=False)
JIT = next(d for d in DOCS if d.metadata["chapter_title"] == "Just-In-Time")
TAKT = JIT.text.split("\n\n")[2]  # the "Takt time is the pace of customer demand..." paragraph


def chunk_cards(chunks, overlap_marks=True, cls=""):
    out, prev = [], ""
    for i, c in enumerate(chunks, 1):
        body = esc(c)
        if overlap_marks and prev:
            # longest prefix of this chunk that is the end of the previous chunk = overlap
            k = max((n for n in range(1, len(c) + 1) if prev.endswith(c[:n])), default=0)
            if k:
                body = f"<span class='ov'>{esc(c[:k])}</span>{esc(c[k:])}"
        out.append(f"<div class='card {cls}'><div class='lbl'><span>Bo‘lak {i}</span><span>{len(c)} belgi</span></div>{body}</div>")
        prev = c
    return "".join(out)


def fig_chunks():
    pieces = RecursiveOverlapSplitter(260, 60).split_text(TAKT)
    body = (f"<h2>Bo‘laklash: bitta abzas → 3 ta bo‘lak (chunk_size = 260, chunk_overlap = 60)</h2>"
            f"<h3>Asl matn ({len(TAKT)} belgi)</h3><div class='card'>{esc(TAKT)}</div>"
            f"<h3>Bo‘laklar <span class='ov'>sariq</span> — oldingi bo‘lakdan takrorlangan qism (overlap)</h3>"
            f"{chunk_cards(pieces)}")
    render_html(body, "fig_chunks.png")


def fig_overlap_problem():
    no = RecursiveOverlapSplitter(260, 0).split_text(TAKT)
    yes = RecursiveOverlapSplitter(260, 60).split_text(TAKT)
    body = (
        "<h2>Nega overlap kerak? Bir xil matn, ikki xil sozlama</h2><div class='row'>"
        f"<div class='col'><h3>❌ Overlap = 0</h3>{chunk_cards(no, False, 'bad')}"
        "<div class='note'>2-bo‘lak “For example, …” bilan boshlanadi — <b>nimaga misol?</b> "
        "Bo‘lakning o‘zida takt time qanday hisoblanishi yo‘q. 3-bo‘lak esa “takt” deydi, lekin 60 soniya haqida bilmaydi.</div></div>"
        f"<div class='col'><h3>✅ Overlap = 60</h3>{chunk_cards(yes, True, 'good')}"
        "<div class='note'>Har bir bo‘lak oldingisining oxiri bilan boshlanadi: 2-bo‘lakda formula davomi, "
        "3-bo‘lakda “takt time is 60 seconds” bor. Har bir bo‘lak <b>alohida o‘qilganda ham tushunarli</b>.</div></div>"
        "</div>")
    render_html(body, "fig_overlap_problem.png")


def fig_chunk_size():
    tiny = RecursiveOverlapSplitter(80, 20).split_text(TAKT)[:3]
    good = RecursiveOverlapSplitter(260, 60).split_text(TAKT)[:1]
    big = JIT.text[:1400] + " …"
    body = (
        "<h2>Bo‘lak hajmini tanlash: juda kichik ↔ me’yorida ↔ juda katta</h2><div class='row'>"
        f"<div class='col'><h3>Juda kichik (80 belgi) <span class='tag t-red'>kontekst yo‘q</span></h3>{chunk_cards(tiny, False, 'bad')}"
        "<div class='note'>“It is calculated by dividing…” — <b>nima</b> hisoblanadi? Bo‘lakning ma’nosi yarim.</div></div>"
        f"<div class='col'><h3>Me’yorida (≈260–800 belgi) <span class='tag t-green'>✓</span></h3>{chunk_cards(good, False, 'good')}"
        "<div class='note'>Bitta to‘liq fikr: ta’rif va qanday hisoblanishi. Qidiruv aniq topadi.</div></div>"
        f"<div class='col'><h3>Juda katta (butun bob) <span class='tag t-red'>aralash</span></h3>"
        f"<div class='card bad' style='font-size:11px;line-height:1.35;white-space:pre-line'>{esc(big)}</div>"
        "<div class='note'>JIT, takt, oqim, kanban — hammasi bitta vektorda “aralashib” ketadi va promptda joy egallaydi.</div></div>"
        "</div>")
    render_html(body, "fig_chunk_size.png")


def fig_cleaning():
    pages = [
        "THE TOYOTA WAY\nKaizen means continuous improve-\nment through many small changes,\nmade by the people who do the work.\n17",
        "THE TOYOTA WAY\nToyota's suggestion system histori-\ncally generated very large numbers of\nideas per employee.\n18",
        "THE TOYOTA WAY\nThe ﬁrst step is always to go and see\nthe actual place where work happens.\n19",
    ]
    cleaned = [clean_text(p) for p in remove_headers_footers(pages)]
    left = "".join(f"<div class='card bad'><div class='lbl'><span>PDF sahifa {i}</span></div><pre>{esc(p)}</pre></div>"
                   for i, p in enumerate(pages, 1))
    right = "".join(f"<div class='card good'><div class='lbl'><span>Sahifa {i} — tozalangan</span></div><pre>{esc(p)}</pre></div>"
                    for i, p in enumerate(cleaned, 1))
    body = (
        "<h2>Tozalash: pypdf bergan xom matn → cleaning.py natijasi (haqiqiy funksiya chiqishi)</h2>"
        f"<div class='row'><div class='col'><h3>Oldin</h3>{left}</div><div class='col'><h3>Keyin</h3>{right}</div></div>"
        "<div class='note'>O‘chirildi: har sahifadagi <b>THE TOYOTA WAY</b> sarlavhasi, sahifa raqamlari <b>17, 18, 19</b>. "
        "Tuzatildi: <b>improve-/ment</b> → improvement, <b>histori-/cally</b> → historically, ligatura <b>ﬁ</b> → fi, "
        "qatorlar abzasga birlashtirildi.</div>")
    render_html(body, "fig_cleaning.png")


def fig_prompt():
    results = [SearchResult("a", TAKT[:166], {**JIT.metadata}, 0.74),
               SearchResult("b", "In continuous flow, parts move one piece at a time from one process step to the next ...",
                            {**JIT.metadata}, 0.61)]
    prompt = build_prompt("How is takt time calculated?", results)
    ins_end = prompt.index("<context>")
    q_start = prompt.index("Question:")
    body = (
        "<h2>Prompt anatomiyasi: modelga aynan nima yuboriladi (rag.py → build_prompt)</h2>"
        "<div class='card'><pre>"
        f"<span class='p-ins'>{esc(prompt[:ins_end])}</span>"
        f"<span class='p-ctx'>{esc(prompt[ins_end:q_start])}</span>"
        f"<span class='p-q'>{esc(prompt[q_start:])}</span></pre></div>"
        "<div class='note'><span class='p-ins'>&nbsp;ko‘k&nbsp;</span> — ko‘rsatma (qoidalar) · "
        "<span class='p-ctx'>&nbsp;sariq&nbsp;</span> — retriever topgan bo‘laklar (kontekst) · "
        "<span class='p-q'>&nbsp;yashil&nbsp;</span> — foydalanuvchi savoli</div>")
    render_html(body, "fig_prompt.png")


# ------------------------------------------------------------------ vector sketches (matplotlib)
TOPICS = {
    "Ishlab chiqarish": (BLUE, {"kanban": (1.0, 4.3), "just-in-time": (1.7, 4.8), "takt vaqti": (2.0, 4.0),
                                "pull tizimi": (0.6, 4.9), "jidoka": (1.3, 3.6)}),
    "Gibrid texnika": (GREEN, {"Prius": (4.8, 1.1), "regenerativ tormoz": (5.5, 1.7), "batareya": (4.3, 0.7),
                               "Atkinson dvigateli": (4.5, 2.0)}),
    "Tarix": (ORANGE, {"Sakichi Toyoda": (4.9, 4.7), "1937-yil": (5.6, 4.2), "Kiichiro": (4.4, 4.1)}),
}


def fig_vectors():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    ax.set_title("Vektor = sonlar ro‘yxati = nuqta / strelka", fontsize=11)
    for (x, y), name, c in [((4, 1), "“kanban” → [4, 1]", BLUE), ((1, 4), "“Prius” → [1, 4]", GREEN)]:
        ax.annotate("", xy=(x, y), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=c, lw=2.2))
        ax.plot([x, x], [0, y], ":", color=c, lw=1)
        ax.plot([0, x], [y, y], ":", color=c, lw=1)
        ax.text(x + 0.1, y + 0.15, name, color=c, fontsize=10, weight="bold")
    ax.set(xlim=(0, 5.8), ylim=(0, 5), xlabel="1-son (masalan: “ishlab chiqarish”ga qanchalik oid)",
           ylabel="2-son (masalan: “texnika”ga qanchalik oid)")
    ax.grid(alpha=.25)

    ax = axes[1]
    ax.set_title("Embedding fazosi: ma’nosi yaqin so‘zlar yaqin joylashadi", fontsize=11)
    for label, (color, pts) in TOPICS.items():
        for i, (name, (x, y)) in enumerate(pts.items()):
            ax.scatter(x, y, s=110, color=color, label=label if i == 0 else None, zorder=3)
            ax.annotate(name, (x, y), xytext=(6, 5), textcoords="offset points", fontsize=9)
    ax.set(xlim=(0, 6.8), ylim=(0.2, 5.6), xticks=[], yticks=[])
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.text(0.5, 0.005, "Soddalashtirilgan sxema: haqiqiy embedding’da 2 emas, yuzlab–minglab son bo‘ladi.",
             ha="center", fontsize=9, color=GREY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig_vectors.png", dpi=150)
    print("  saved fig_vectors.png")


def fig_cosine():
    cases = [("Ma’nosi yaqin", (4, 3), (3.6, 3.6), "“kanban” va\n“pull tizimi”"),
             ("Bog‘liq emas", (4, 1), (0.6, 4), "“Prius” va\n“takt vaqti”"),
             ("Qarama-qarshi", (3, 2.4), (-3, -2.2), "matn va uning\nteskari ma’nosi")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.9))
    for ax, (title, a, b, desc) in zip(axes, cases):
        a, b = np.array(a, float), np.array(b, float)
        cos = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
        deg = np.degrees(np.arccos(np.clip(cos, -1, 1)))
        for v, c in ((a, BLUE), (b, RED)):
            ax.annotate("", xy=v, xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=c, lw=2.4))
        t0, t1 = sorted([np.arctan2(a[1], a[0]), np.arctan2(b[1], b[0])])
        if t1 - t0 > np.pi:
            t0, t1 = t1, t0 + 2 * np.pi
        th = np.linspace(t0, t1, 40)
        ax.plot(0.9 * np.cos(th), 0.9 * np.sin(th), color=GREY)
        ax.set_title(f"{title}\nburchak ≈ {deg:.0f}°   cos = {cos:.2f}", fontsize=11)
        ax.text(0.5, -0.08, desc.replace("\n", " "), transform=ax.transAxes, ha="center", va="top", fontsize=9, color=GREY)
        ax.set(xlim=(-4.5, 5), ylim=(-4, 5), xticks=[], yticks=[], aspect="equal")
        ax.axhline(0, color="#e5e7eb", lw=1, zorder=0)
        ax.axvline(0, color="#e5e7eb", lw=1, zorder=0)
    fig.suptitle("Kosinus o‘xshashligi: strelkalar orasidagi burchak qancha kichik bo‘lsa, ma’no shuncha yaqin",
                 fontsize=11, y=0.99)
    fig.tight_layout(rect=(0, 0.06, 1, 0.9))
    fig.savefig(OUT / "fig_cosine.png", dpi=150)
    print("  saved fig_cosine.png")


def fig_search():
    pts = [(n, xy, c) for _, (c, d) in TOPICS.items() for n, xy in d.items()]
    q = np.array([1.5, 4.45])
    sims = []
    for name, xy, c in pts:
        v = np.array(xy)
        sims.append(float(np.linalg.norm(v - q)))
    order = np.argsort(sims)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for rank, idx in enumerate(order, 1):
        name, (x, y), c = pts[idx]
        top = rank <= 4
        ax.scatter(x, y, s=150 if top else 90, color=c, alpha=1 if top else .35, zorder=3,
                   edgecolor="black" if top else "none", linewidth=1.5)
        left = top and x < q[0]          # labels left of the question go on the left side
        ax.annotate(f"{name}" + (f"  #{rank}" if top else ""), (x, y), xytext=(-9 if left else 7, 5),
                    textcoords="offset points", ha="right" if left else "left",
                    fontsize=9, weight="bold" if top else "normal", alpha=1 if top else .5)
        if top:
            ax.plot([q[0], x], [q[1], y], color="black", lw=.8, alpha=.5)
    ax.scatter(*q, marker="*", s=480, color="black", zorder=4)
    ax.annotate("★ = savol: “What is just-in-time?”", q, xytext=(2.6, 3.0), fontsize=10, weight="bold",
                arrowprops=dict(arrowstyle="->", color="black", lw=1))
    r = sims[order[3]] + 0.12
    ax.add_patch(plt.Circle(q, r, fill=False, ls="--", color=GREY))
    ax.text(q[0] - r * 0.95, q[1] - r * 1.15, "top-k = 4 doirasi", color=GREY, fontsize=9)
    ax.set_aspect("equal")
    ax.set(xlim=(0, 6.8), ylim=(0.2, 5.8), xticks=[], yticks=[],
           title="Retriever: savolga eng yaqin k ta bo‘lakni topadi (soddalashtirilgan sxema)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_search.png", dpi=150)
    print("  saved fig_search.png")


def fig_topk():
    ks = [1, 2, 3, 4, 6, 8, 12]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(ks, [40, 62, 75, 83, 88, 90, 91], "-o", color=GREEN, label="To‘g‘ri bo‘lak topilish ehtimoli (hit@k)")
    ax.plot(ks, [5, 10, 15, 20, 30, 40, 60], "-o", color=RED, label="Promptdagi “shovqin” va uzunlik")
    ax.axvspan(3, 6, color=BLUE, alpha=.08)
    ax.text(4.5, 50, "odatda\neng yaxshi\nk = 3…6", ha="center", color=BLUE)
    ax.set(xlabel="k — nechta bo‘lak olinadi", ylabel="nisbiy qiymat", xticks=ks, yticks=[],
           title="k ni tanlash: ko‘proq bo‘lak = javob topilishi ehtimoli ↑, lekin shovqin ham ↑ (sxema)")
    ax.title.set_fontsize(10)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_topk.png", dpi=150)
    print("  saved fig_topk.png")


if __name__ == "__main__":
    fig_vectors()
    fig_cosine()
    fig_search()
    fig_topk()
    fig_chunks()
    fig_overlap_problem()
    fig_chunk_size()
    fig_cleaning()
    fig_prompt()
