# -*- coding: utf-8 -*-
"""Наполнение колоды C1.

    python vocabulario/c1.py novas    — какие слова из _c1-candidatas.txt ещё не заняты
    python vocabulario/c1.py add      — добавить порцию из _c1-porcao.py
    python vocabulario/c1.py stat     — сколько карточек в какой теме
    python vocabulario/c1.py check    — прогнать чек-лист качества по всем колодам

Колода C1 устроена как B1 и B2: файла тем у неё нет, уровень и тема лежат
в самой карточке и расставляются руками. Уровень у всех карточек один — C1,
поэтому в порции его нет, скрипт проставляет его сам.

Порция пишется в vocabulario/_c1-porcao.py (в репозиторий не входит) списком
кортежей КАРТОЧКИ вида (слово, часть речи, тема, перевод, пример, перевод примера,
заметка). Как и lacunas.py, `add` не пишет ничего, пока есть хоть одно замечание.

Список кандидатов — vocabulario/_c1-candidatas.txt, по слову в строке; пустые
строки и строки с # пропускаются. `novas` вычитает из него всё, что уже занято
любой из колод, и печатает остаток. Ничего не решает за человека: отбор
по-прежнему глазами, скрипт лишь снимает уже написанное.
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
УРОВНИ = ("A1", "A2", "B1", "B2", "C1")
КОЛОДЫ = {ур: os.path.join(ЗДЕСЬ, "baralho-completo-%s.json" % ур) for ур in УРОВНИ}
ПОРЦИЯ = os.path.join(ЗДЕСЬ, "_c1-porcao.py")
КАНДИДАТЫ = os.path.join(ЗДЕСЬ, "_c1-candidatas.txt")

АРТИКЛЬ = re.compile(r"^(o|a|os|as|um|uma)\s+")
ПУНКТУАЦИЯ = re.compile(r"[.,;:!?\"'()]")

# Темы словника Referencial Camões PLE — те же, что в temas.py и index.html.
ИМЕНА = {
    "A1": "Бытие", "A2": "Пространство", "A3": "Размер и форма", "A4": "Время",
    "A5": "Количество", "A6": "Качества", "A7": "Оценка", "A8": "Мышление и речь",
    "A9": "Связки и отношения", "B1": "Личные данные", "B2": "Дом и окружение",
    "B3": "Повседневная жизнь", "B4": "Досуг", "B5": "Поездки и транспорт",
    "B6": "Здоровье и гигиена", "B7": "Покупки", "B8": "Еда", "B9": "Услуги",
}


def norm(s):
    """То же, что norm() в index.html и public.pt_norm() в базе."""
    s = (s or "").lower()
    return ПУНКТУАЦИЯ.sub("", АРТИКЛЬ.sub("", s)).strip()


def читать(п):
    return json.load(io.open(п, encoding="utf-8"))


def писать(п, данные):
    io.open(п, "w", encoding="utf-8", newline="").write(
        json.dumps(данные, ensure_ascii=False, indent=1))


def своя():
    """Колода C1; заводится пустой, если файла ещё нет."""
    if not os.path.exists(КОЛОДЫ["C1"]):
        return {"v": 1, "deck": "c1", "cards": []}
    return читать(КОЛОДЫ["C1"])


def все_карточки():
    """Карточки всех колод вместе — против них проверяются повторы."""
    out = []
    for ур in УРОВНИ:
        out += (своя() if ур == "C1" else читать(КОЛОДЫ[ур]))["cards"]
    return out


def слова_примера(ex):
    """Множество слов примера — по нему сравниваются похожие предложения."""
    return set(ПУНКТУАЦИЯ.sub(" ", (ex or "").lower()).split())


def похожие_примеры(помеченные, порог=0.6):
    """Пары примеров, различающихся одним-двумя словами.

    Точное сравнение строк такие пары не ловит: «Ouço rádio no carro» и
    «Ouço a rádio no carro» — разные строки, но одно и то же предложение,
    и две карточки учат ему обе. Сравниваем множества слов: пересечение,
    делённое на объединение, у близнецов выходит выше 0.6.

    Чтобы не гонять четыре с половиной тысячи примеров каждый с каждым,
    кандидаты берём по обратному указателю: сравниваем только те пары,
    что делят хотя бы одно нечастое слово. Артикли и предлоги для этого
    бесполезны — они есть почти везде, поэтому слова частотнее ЧАСТОЕ
    в указатель не идут.
    """
    ЧАСТОЕ = 200
    указатель = collections.defaultdict(list)
    наборы = []
    for i, (метка, ex) in enumerate(помеченные):
        s = слова_примера(ex)
        наборы.append((метка, ex, s))
        for w in s:
            указатель[w].append(i)

    пары, видели = [], set()
    for w, кто in указатель.items():
        if len(кто) > ЧАСТОЕ:
            continue
        for a in range(len(кто)):
            for b in range(a + 1, len(кто)):
                i, j = кто[a], кто[b]
                if (i, j) in видели:
                    continue
                видели.add((i, j))
                si, sj = наборы[i][2], наборы[j][2]
                if len(si) < 4 or len(sj) < 4:
                    continue
                общих = len(si & sj)
                сходство = общих / float(len(si | sj))
                if сходство >= порог:
                    пары.append((сходство, наборы[i][0], наборы[i][1],
                                 наборы[j][0], наборы[j][1]))
    пары.sort(reverse=True)
    return пары


def свободны(слова, карточки):
    """(свободные, занятые) — по norm(), плюс вхождение словом в словосочетание."""
    занято = {norm(c["word"]) for c in карточки}
    тексты = [c["word"].lower() for c in карточки]
    свободные, заняты = [], []
    for w in слова:
        k = norm(w)
        есть = k in занято or any(
            re.search(r"\b" + re.escape(k) + r"\b", t) for t in тексты)
        (заняты if есть else свободные).append(w)
        занято.add(k)
    return свободные, заняты


def кандидаты():
    if not os.path.exists(КАНДИДАТЫ):
        return []
    строки = io.open(КАНДИДАТЫ, encoding="utf-8").read().splitlines()
    слова = [s.strip() for s in строки]
    return [s for s in слова if s and not s.startswith("#")]


def проверить(порция, карточки):
    """Замечания по порции. Пусто — можно писать."""
    было = {norm(c["word"]) for c in карточки}
    переводы, примеры = {}, {}
    for c in карточки:
        переводы.setdefault(c["ru"].strip().lower(), []).append(c["word"])
        примеры.setdefault(c["ex"].strip().lower(), []).append(c["word"])

    замечания = []
    for кортеж in порция:
        if len(кортеж) != 7:
            замечания.append("в кортеже %d полей вместо 7: %s" % (len(кортеж), кортеж[0]))
            continue
        w, pos, tema, ru, ex, exru, note = кортеж
        k = norm(w)
        if k in было:
            замечания.append("уже есть: " + w)
        было.add(k)
        if tema not in ИМЕНА:
            замечания.append("нет такой темы «%s»: %s" % (tema, w))
        ключ_ru = ru.strip().lower()
        if ключ_ru in переводы:
            замечания.append("одинаковый перевод «%s»: %s и %s"
                             % (ru, переводы[ключ_ru][0], w))
        переводы.setdefault(ключ_ru, []).append(w)
        ключ_ex = ex.strip().lower()
        if ключ_ex in примеры:
            замечания.append("пример повторяет карточку %s: %s" % (примеры[ключ_ex][0], w))
        примеры.setdefault(ключ_ex, []).append(w)
        n = len(ex.split())
        if not 7 <= n <= 14:
            замечания.append("пример из %d слов: %s" % (n, w))
        if len(note) > 90:
            замечания.append("заметка длиннее 90 символов: " + w)
        if not (w and ru and ex and exru and pos):
            замечания.append("пустое поле: " + w)
    return замечания


def добавить():
    spec = importlib.util.spec_from_file_location("porcao", ПОРЦИЯ)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    порция = m.КАРТОЧКИ

    замечания = проверить(порция, все_карточки())
    if замечания:
        return 0, замечания

    колода = своя()
    for w, pos, tema, ru, ex, exru, note in порция:
        колода["cards"].append({"word": w, "pos": pos, "level": "C1", "ru": ru,
                                "ex": ex, "exru": exru, "note": note, "tema": tema})
    писать(КОЛОДЫ["C1"], колода)
    return len(порция), []


def статистика():
    карточки = своя()["cards"]
    счёт = collections.Counter(c.get("tema") or "—" for c in карточки)
    части = collections.Counter(c["pos"] for c in карточки)
    for тема, n in sorted(счёт.items()):
        print("%-4s %-22s %4d" % (тема, ИМЕНА.get(тема, "без темы"), n))
    print("%-27s %4d" % ("всего", sum(счёт.values())))
    print()
    print("части речи: " + ", ".join("%s %d" % (k, v) for k, v in части.most_common()))


def чек_лист():
    """Тот же список, что в CLAUDE.md: дубли, переводы, примеры, пустые поля."""
    по_слову, по_переводу, по_примеру, по_переводу_примера = {}, {}, {}, {}
    коротко, длинно, пусто, без_темы = [], [], [], []
    помеченные = []
    for ур in УРОВНИ:
        колода = своя() if ур == "C1" else читать(КОЛОДЫ[ур])
        for c in колода["cards"]:
            метка = "%s:%s" % (ур, c["word"])
            по_слову.setdefault(norm(c["word"]), []).append(метка)
            по_переводу.setdefault(c["ru"].strip().lower(), []).append(метка)
            по_примеру.setdefault(c["ex"].strip().lower(), []).append(метка)
            по_переводу_примера.setdefault(c["exru"].strip().lower(), []).append(метка)
            помеченные.append((метка, c["ex"]))
            n = len(c["ex"].split())
            if n < 7:
                коротко.append(метка)
            if n > 14:
                длинно.append(метка)
            if not all(c.get(поле) for поле in ("word", "pos", "ru", "ex", "exru")):
                пусто.append(метка)
            if ур in ("B1", "B2", "C1") and not c.get("tema"):
                без_темы.append(метка)

    def показать(имя, карта):
        плохо = {k: v for k, v in карта.items() if len(v) > 1}
        print("%-24s %d" % (имя, len(плохо)))
        for k, v in list(плохо.items())[:10]:
            print("    %s — %s" % (k, ", ".join(v)))

    показать("повторы слов:", по_слову)
    показать("одинаковый перевод:", по_переводу)
    показать("одинаковый пример:", по_примеру)
    # Русский перевод примера traduzir.py не проверяет: он занят uk и en,
    # а русский для него — запасной язык, не один из переводимых.
    показать("одинаковый перевод примера:", по_переводу_примера)

    близнецы = похожие_примеры(помеченные)
    print("%-24s %d" % ("похожий пример:", len(близнецы)))
    for сходство, м1, e1, м2, e2 in близнецы[:20]:
        print("    %.2f  %s — %s" % (сходство, м1, e1))
        print("          %s — %s" % (м2, e2))

    print("%-24s %d" % ("пример короче 7 слов:", len(коротко)))
    print("%-24s %d %s" % ("пример длиннее 14:", len(длинно), ", ".join(длинно[:10])))
    print("%-24s %d %s" % ("пустое поле:", len(пусто), ", ".join(пусто[:10])))
    print("%-24s %d %s" % ("без темы:", len(без_темы), ", ".join(без_темы[:10])))


if __name__ == "__main__":
    что = sys.argv[1] if len(sys.argv) > 1 else "stat"
    if что == "add":
        n, замечания = добавить()
        if замечания:
            print("не записано, замечаний %d:" % len(замечания))
            for з in замечания:
                print("  " + з)
            raise SystemExit(1)
        print("добавлено: %d, всего в C1: %d" % (n, len(своя()["cards"])))
    elif что == "novas":
        свободные, заняты = свободны(кандидаты(), все_карточки())
        print("кандидатов %d, занято %d, свободно %d\n"
              % (len(свободные) + len(заняты), len(заняты), len(свободные)))
        print("занято: " + ", ".join(заняты) + "\n")
        print("\n".join(свободные))
    elif что == "check":
        чек_лист()
    else:
        статистика()
