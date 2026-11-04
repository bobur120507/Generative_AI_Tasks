# Modda — interfeys prototipi

Bu papkada Modda saytining ishlaydigan prototipi bor: 3D kitob, manbali javob, chetdagi izohlar, toʻliq modda paneli. Server boʻlmasa, sahifa `mock-data.js` dagi **namuna** maʼlumotlar bilan ishlaydi (namuna qonun haqiqiy hujjat emas).

## Ishga tushirish

```bash
cd frontend
python3 -m http.server 8000
# brauzerda: http://localhost:8000
```

`index.html` ni toʻgʻridan-toʻgʻri ochish ham mumkin — u holda doim namuna rejimi.

Sinab koʻrish uchun:

| Savol | Natija |
|---|---|
| «Oʻquv taʼtili necha kun beriladi?» | Javob, ikki manba |
| «Taʼtil haqi qachon toʻlanadi?» | Javob + «oʻzgargan boʻlishi mumkin» ogohlantirishi |
| Taʼtilga aloqasiz istalgan savol | «Bilmayman» |
| `index.html?demo=error&q=test` | Server xatosi holati |
| `index.html?q=...` | Savolni darhol yuborish |

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `index.html` | Sahifa tuzilmasi |
| `styles.css` | Ranglar, shriftlar, 3D kitob, animatsiyalar, telefon va qorongʻi rejim |
| `app.js` | Holatlar, javobni chizish, izohlarni joylash, egri chiziqlar, modda paneli, API |
| `mock-data.js` | Namuna javoblar; ular API shartnomasining namunasi ham |

## FastAPI’ni ulash (3-kun)

Sahifa API’ni shu tartibda qidiradi:

1. `window.MODDA_API` berilgan boʻlsa — oʻsha manzil (`index.html` da `app.js` dan oldin `<script>window.MODDA_API = "http://localhost:8080";</script>`). Server xato qaytarsa, **xato holati** koʻrsatiladi.
2. Berilmagan boʻlsa — sahifa bilan bir xil manzil (FastAPI `StaticFiles` bilan shu papkani bersa, qulay). Server topilmasa — namuna rejimi.

Boshqa manzildan ulansa, FastAPI’da CORS yoqiladi (`CORSMiddleware`).

### `GET /health` (ixtiyoriy)

```json
{ "checked_at": "2026-11-01" }
```

Sarlavhadagi holat yozuvi uchun. Boʻlmasa ham sahifa ishlaydi.

### `POST /ask`

Soʻrov:

```json
{ "question": "Oʻquv taʼtili necha kun beriladi?" }
```

Javob:

```json
{
  "unknown": false,
  "checked_at": "2026-11-01",
  "answer": [
    {
      "text": "Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.",
      "chunk_ids": ["doc#m3"],
      "quote": "kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi"
    }
  ],
  "sources": {
    "doc#m3": {
      "title": "«Oʻquv namunasi» toʻgʻrisidagi Qonun",
      "doc_type": "Qonun",
      "doc_number": "OʻRQ-000",
      "adoption_date": "2026-01-15",
      "url": "https://lex.uz/docs/...",
      "article_no": "3",
      "article_title": "Taʼtil muddati",
      "text": "Moddaning toʻliq matni.\nHar bir qism yangi qatordan.",
      "amendment_note": "… tahririda",
      "stale": false
    }
  }
}
```

Qoidalar:

* `answer` — **faqat tekshiruvdan oʻtgan** gaplar (verifier va τ backend’da ishlaydi). Interfeys har bir gapni «tasdiqlangan» deb koʻrsatadi.
* `quote` — `sources[id].text` ichida **aynan** bor boʻlgan qism (katta-kichik harf farqi mumkin). Panel shu qismni belgilaydi.
* `sources` dagi hamma maydon **metadata’dan kod bilan** toʻldiriladi, model yozmaydi.
* `stale: true` — hujjat RSS’da yaqinda oʻzgargan, lekin indeks hali yangilanmagan.
* «Bilmayman»: `{"unknown": true, "checked_at": "...", "answer": [], "sources": {}}`.
* HTTP xato yoki 60 soniyadan uzoq kutish — xato holati va «Qayta urinish».

## Tekshirilgan

Playwright bilan: kompyuter (1360 px) va telefon (390 px), yorugʻ va qorongʻi rejim, `prefers-reduced-motion`, barcha holatlar, klaviatura (Enter yuboradi, Esc panelni yopadi, fokus panel ichida qoladi va qaytadi), gorizontal aylantirish yoʻq. Shriftlar (Onest, Literata) Google Fonts’dan yuklanadi; tarmoq boʻlmasa Inter va Lora ishlatiladi.
