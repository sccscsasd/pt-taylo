// Прокси к OpenAI для приложения pt.taylo.co.
//
// Ключ OpenAI живёт здесь, в секретах Supabase, и в браузер не попадает.
// Клиент присылает только слова или картинку:
//   { mode: "cards",  items: [{ word: "arrumar", context?: "…" }] }
//   { mode: "vision", image: "data:image/jpeg;base64,…" }
//
// Секреты (Supabase → Edge Functions → Secrets):
//   OPENAI_API_KEY  — обязательный
//   OPENAI_MODEL    — необязательный, по умолчанию gpt-4o-mini
//   DAILY_LIMIT     — необязательный, запросов с одного IP в сутки, по умолчанию 300

const OPENAI_KEY = Deno.env.get("OPENAI_API_KEY") ?? "";
const MODEL = Deno.env.get("OPENAI_MODEL") ?? "gpt-4o-mini";
const DAILY_LIMIT = Number(Deno.env.get("DAILY_LIMIT") ?? "300");
const SB_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SB_SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const MAX_ITEMS = 20;
const MAX_IMAGE_CHARS = 6_000_000; // ~4,4 МБ картинки в base64

const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const SYS = `Ты — лексикограф европейского португальского (PT-PT, Португалия; НЕ бразильский вариант).
На вход даётся список слов/выражений, у некоторых есть "context" — предложение, из которого слово взято.
Для каждого элемента верни объект:
- "input": исходная строка "word" дословно, как пришла (для сопоставления).
- "word": начальная форма в PT-PT. Существительные — с определённым артиклем ("o carro", "a chave"). Глаголы — инфинитив. Прилагательные — муж. род ед. ч. Выражения — как есть.
- "pos": часть речи по-русски кратко: сущ., глаг., прил., нареч., предл., мест., выраж.
- "ru": перевод на русский, 1–3 значения через запятую, самое частотное первым.
- "example_pt": ОДНО естественное предложение на европейском португальском, 7–14 слов, уровень A2–B1, слово в живом контексте. Если дан "context" — строй пример вокруг той же ситуации.
- "example_ru": перевод примера на русский, естественный, не подстрочник.
- "note": максимум 90 символов — самое важное: род, неправильное мн. ч. или спряжение, требуемый предлог, ложный друг. Бразильские варианты не упоминай. Если нечего сказать — пустая строка "".
Отвечай ТОЛЬКО валидным JSON без markdown: {"cards":[...]}`;

const VSYS = `Ты распознаёшь текст на изображении (скриншот, фото страницы, субтитры, вывеска) и переводишь его на русский.
Верни ТОЛЬКО валидный JSON без markdown:
{"text":"<весь текст с картинки дословно, с диакритикой и пунктуацией; абзацы разделяй \\n>",
 "ru":"<естественный литературный перевод на русский>",
 "lang":"<код языка оригинала: pt, en, es, ru…>"}
Если текста на картинке нет — {"text":"","ru":"","lang":""}.`;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });

/** Счётчик запросов на IP в сутки. Если база недоступна — не блокируем работу. */
async function withinLimit(ip: string): Promise<boolean> {
  if (!SB_URL || !SB_SERVICE) return true;
  try {
    const r = await fetch(`${SB_URL}/rest/v1/rpc/pt_bump_usage`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SB_SERVICE,
        Authorization: `Bearer ${SB_SERVICE}`,
      },
      body: JSON.stringify({ p_ip: ip, p_limit: DAILY_LIMIT }),
    });
    if (!r.ok) return true;
    return (await r.json()) !== false;
  } catch {
    return true;
  }
}

async function askOpenAI(messages: unknown[]): Promise<Record<string, unknown>> {
  const r = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${OPENAI_KEY}`,
    },
    body: JSON.stringify({
      model: MODEL,
      messages,
      temperature: 0.3,
      response_format: { type: "json_object" },
    }),
  });
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json())?.error?.message ?? "";
    } catch { /* пустой ответ */ }
    throw new Error(`OpenAI ${r.status}: ${detail || r.statusText}`);
  }
  const data = await r.json();
  const text = data?.choices?.[0]?.message?.content ?? "{}";
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("Модель вернула не-JSON");
  }
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "Только POST" }, 405);
  if (!OPENAI_KEY) return json({ error: "На сервере не задан OPENAI_API_KEY" }, 503);

  const ip = (req.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "unknown";
  if (!(await withinLimit(ip))) {
    return json({ error: "Дневной лимит запросов исчерпан, попробуйте завтра" }, 429);
  }

  let body: { mode?: string; items?: unknown[]; image?: string };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Ожидается JSON" }, 400);
  }

  try {
    if (body.mode === "cards") {
      const items = Array.isArray(body.items) ? body.items.slice(0, MAX_ITEMS) : [];
      if (!items.length) return json({ error: "Пустой список слов" }, 400);
      const out = await askOpenAI([
        { role: "system", content: SYS },
        { role: "user", content: JSON.stringify({ items }) },
      ]);
      return json(out);
    }

    if (body.mode === "vision") {
      const image = typeof body.image === "string" ? body.image : "";
      if (!image.startsWith("data:image/")) return json({ error: "Ожидается картинка" }, 400);
      if (image.length > MAX_IMAGE_CHARS) return json({ error: "Картинка слишком большая" }, 413);
      const out = await askOpenAI([
        { role: "system", content: VSYS },
        {
          role: "user",
          content: [
            { type: "text", text: "Распознай текст на этом изображении и переведи его на русский." },
            { type: "image_url", image_url: { url: image, detail: "high" } },
          ],
        },
      ]);
      return json(out);
    }

    return json({ error: "Неизвестный режим" }, 400);
  } catch (e) {
    return json({ error: (e as Error).message }, 502);
  }
});
