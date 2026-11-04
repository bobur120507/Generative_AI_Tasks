// Sample data for the prototype. The law below is a TRAINING SAMPLE
// ("Oʻquv namunasi"), not a real legal act. The shape of every object is the
// API contract that FastAPI's POST /ask must return (see frontend/README.md).

const SAMPLE_DOC = {
  title: "«Oʻquv namunasi» toʻgʻrisidagi Qonun",
  doc_type: "Qonun",
  doc_number: "OʻRQ-000",
  adoption_date: "2026-01-15",
  url: "https://lex.uz/",
};

const SAMPLE_SOURCES = {
  "doc#m3": {
    ...SAMPLE_DOC,
    article_no: "3",
    article_title: "Taʼtil muddati",
    text: "Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.\nTaʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin.",
    amendment_note: "Namuna qonunining 2026-yil 1-martdagi tahririda",
    stale: false,
  },
  "doc#m4": {
    ...SAMPLE_DOC,
    article_no: "4",
    article_title: "Taʼtil haqi",
    text: "Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi.\nTaʼtil haqi xodimning oʻrtacha ish haqidan kelib chiqib hisoblanadi.",
    amendment_note: null,
    stale: false,
  },
};

const SCENARIOS = {
  leave: {
    unknown: false,
    checked_at: "2026-11-01",
    answer: [
      { text: "Xodimga har yili kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi.",
        chunk_ids: ["doc#m3"], quote: "kamida 21 kalendar kun haq toʻlanadigan taʼtil beriladi" },
      { text: "Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin.",
        chunk_ids: ["doc#m3"], quote: "Taʼtil xodimning arizasiga koʻra qismlarga boʻlinishi mumkin" },
      { text: "Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi.",
        chunk_ids: ["doc#m4"], quote: "taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi" },
    ],
    sources: SAMPLE_SOURCES,
  },
  pay: {
    unknown: false,
    checked_at: "2026-11-01",
    answer: [
      { text: "Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi.",
        chunk_ids: ["doc#m4"], quote: "Taʼtil haqi taʼtil boshlanishidan kamida 3 kun oldin toʻlanadi" },
      { text: "Uning miqdori xodimning oʻrtacha ish haqidan kelib chiqib hisoblanadi.",
        chunk_ids: ["doc#m4"], quote: "xodimning oʻrtacha ish haqidan kelib chiqib hisoblanadi" },
    ],
    sources: { "doc#m4": { ...SAMPLE_SOURCES["doc#m4"], stale: true } },
  },
  unknown: { unknown: true, checked_at: "2026-11-01", answer: [], sources: {} },
};

const EXAMPLES = [
  { text: "Oʻquv taʼtili necha kun beriladi?", hint: "Javob va ikki manba" },
  { text: "Taʼtil haqi qachon toʻlanadi?", hint: "Yaqinda oʻzgargan boʻlishi mumkin" },
  { text: "Kosmik turizm uchun soliq imtiyozi bormi?", hint: "Bazada javob yoʻq" },
];

function mockAsk(question) {
  const q = question.toLowerCase().replace(/[ʻʼ'’‘`ъ]/g, "");   // "taʼtil" -> "tatil", "таътил" -> "таътил" without ъ
  let key = "unknown";
  const leave = /tatil|таътил|татил|отпуск/.test(q);
  if (leave && /haqi|tolan|ҳақи|тўлан/.test(q)) key = "pay";
  else if (leave) key = "leave";
  return new Promise((resolve) => setTimeout(() => resolve(structuredClone(SCENARIOS[key])), 2600));
}
