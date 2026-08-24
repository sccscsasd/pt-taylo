# -*- coding: utf-8 -*-
"""Один шаг работы над колодой B1–B2.

    python vocabulario/b1b2-passo.py next   — показать следующие 120 кандидатов
    python vocabulario/b1b2-passo.py add    — добавить написанные карточки и показать следующие

Карточки пишутся руками в vocabulario/_b1b2-porcao.py — список кортежей КАРТОЧКИ вида
(слово, часть речи, уровень, перевод, пример, перевод примера, заметка). Скрипт их
дописывает в колоду по уровню (B1 или B2 — это разные колоды), проверяет на повторы,
одинаковые переводы и длину примера, а всё показанное и не ставшее карточкой заносит
в b1b2-rejeitadas.txt: это решение «просмотрено и не взято», без него слова
возвращались бы в список по кругу.

Выгрузка просмотрена до конца — «осталось просмотреть: 0». Скрипт лежит здесь ради
истории и на случай, если появится новая выгрузка; для добора карточек по темам
есть lacunas.py.
"""
import io, json, os, re, sys, importlib.util

БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
СЛОВ = 120
ФАЙЛЫ = {"B1": os.path.join(БАЗА, "vocabulario", "baralho-completo-B1.json"),
         "B2": os.path.join(БАЗА, "vocabulario", "baralho-completo-B2.json")}
ОТКАЗ = os.path.join(БАЗА, "vocabulario", "b1b2-rejeitadas.txt")
A1A2 = [os.path.join(БАЗА, "vocabulario", "baralho-completo-A1.json"),
        os.path.join(БАЗА, "vocabulario", "baralho-completo-A2.json")]
ИСТ = r"E:/other/chrome/portuguese_PTPT_B1_B2_3000_clean_candidate.xlsx"
ЖДУТ = os.path.join(БАЗА, "vocabulario", "_b1b2-ждут.txt")
ПОРЦИЯ = os.path.join(БАЗА, "vocabulario", "_b1b2-porcao.py")


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"^(o|a|os|as|um|uma)\s+", "", s)
    return re.sub(r"[.,;:!?\"'()]", "", s).strip()


def колода(п, пусто=None):
    if not os.path.exists(п):
        return пусто if пусто is not None else {"v": 1, "deck": "b1", "cards": []}
    return json.load(io.open(п, encoding="utf-8"))


def слова_из(п):
    return {norm(c["word"]) for c in колода(п, {"cards": []})["cards"]}


def слова_b():
    """Слова обеих колод B1 и B2 — они лежат в разных файлах."""
    вместе = set()
    for п in ФАЙЛЫ.values():
        вместе |= слова_из(п)
    return вместе


def слова_a():
    """То же для базовых колод A1 и A2."""
    вместе = set()
    for п in A1A2:
        вместе |= слова_из(п)
    return вместе


def отклонённые():
    if not os.path.exists(ОТКАЗ):
        return [], []
    строки = io.open(ОТКАЗ, encoding="utf-8").read().split("\n")
    шапка = [l for l in строки if l.startswith("#")]
    слова = [l.strip() for l in строки if l.strip() and not l.startswith("#")]
    return шапка, слова


def источник():
    import openpyxl
    строки = list(openpyxl.load_workbook(ИСТ, read_only=True)["Sheet1"].iter_rows(values_only=True))[1:]
    POS = {"noun": "сущ.", "Noun": "сущ.", "verb": "глаг.", "Verb": "глаг.", "adj": "прил.",
           "Adjective": "прил.", "adv": "нареч.", "Adverb": "нареч.", "interj": "межд.",
           "pron": "мест.", "prep": "предл.", "conj": "союз"}
    return [((r[1] or "").strip(), r[2], POS.get(r[3], "?")) for r in строки if (r[1] or "").strip()]


def добавить():
    spec = importlib.util.spec_from_file_location("porcao", ПОРЦИЯ)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    d = {ур: колода(п) for ур, п in ФАЙЛЫ.items()}
    было = слова_b()
    базовые = слова_a()
    переводы = {}
    for к in d.values():
        for c in к["cards"]:
            переводы.setdefault(c["ru"], []).append(c["word"])
    добавлено, замечания = 0, []
    for w, pos, lvl, ru, ex, exru, note in m.КАРТОЧКИ:
        k = norm(w)
        if k in базовые or k in было:
            замечания.append("пропущено (уже есть): " + w); continue
        if ru in переводы:
            замечания.append("одинаковый перевод «%s»: %s и %s" % (ru, переводы[ru][0], w))
        n = len(ex.split())
        if not (7 <= n <= 14):
            замечания.append("пример из %d слов: %s" % (n, w))
        if len(note) > 90:
            замечания.append("длинная заметка: " + w)
        if lvl not in d:
            замечания.append("непонятный уровень «%s»: %s" % (lvl, w)); continue
        d[lvl]["cards"].append({"word": w, "pos": pos, "level": lvl, "ru": ru,
                                "ex": ex, "exru": exru, "note": note})
        было.add(k); переводы.setdefault(ru, []).append(w); добавлено += 1
    for ур, п in ФАЙЛЫ.items():
        io.open(п, "w", encoding="utf-8", newline="").write(
            json.dumps(d[ур], ensure_ascii=False, indent=1))
    return добавлено, sum(len(к["cards"]) for к in d.values()), замечания


def отметить():
    """Всё, что было показано в прошлый раз и не стало карточкой, — отклонено."""
    if not os.path.exists(ЖДУТ):
        return 0
    показано = [l.strip() for l in io.open(ЖДУТ, encoding="utf-8") if l.strip()]
    взято = слова_b() | слова_a()
    шапка, уже = отклонённые()
    новые = [w for w in показано if norm(w) not in взято and w not in уже]
    if not шапка:
        шапка = ["# Слова из выгрузки B1–B2, просмотренные и не взятые в колоду.",
                 "# Причины: словоформа вместо леммы, бразильский вариант, слишком редкое или узкое,",
                 "# непристойное, обрубок слова, дубль по смыслу, уже покрыто колодой A1–A2."]
    io.open(ОТКАЗ, "w", encoding="utf-8", newline="").write("\n".join(шапка) + "\n" + "\n".join(уже + новые) + "\n")
    return len(новые)


def следующие():
    готово = слова_b() | слова_a() | {norm(w) for w in отклонённые()[1]}
    ждут = [x for x in источник() if norm(x[0]) not in готово]
    порция = ждут[:СЛОВ]
    io.open(ЖДУТ, "w", encoding="utf-8", newline="").write("\n".join(w for w, _, _ in порция) + "\n")
    return ждут, порция


if __name__ == "__main__":
    что = sys.argv[1] if len(sys.argv) > 1 else "next"
    if что == "add":
        n, всего, зам = добавить()
        отк = отметить()
        print("добавлено %d, в колоде %d, отклонено на этом шаге %d" % (n, всего, отк))
        for z in зам:
            print("  " + z)
    ждут, порция = следующие()
    print("\nосталось просмотреть: %d" % len(ждут))
    print(", ".join("%s [%s %s]" % (w, l, p) for w, l, p in порция))
