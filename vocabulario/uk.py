# -*- coding: utf-8 -*-
"""Украинский перевод карточек колоды: партиями, с проверкой каждой.

Переводится оборот карточки — перевод, перевод примера и заметка. Слово и пример
по-португальски у карточки одни на все языки и не трогаются.

    python vocabulario/uk.py next [N]   показать следующие N непереведённых
    python vocabulario/uk.py add        влить партию из _uk-porcao.json
    python vocabulario/uk.py stat       сколько переведено
    python vocabulario/uk.py check      чек-лист качества по всей колоде

Партия — _uk-porcao.json, список объектов {"word", "uk", "exuk", "noteuk"}.
JSON, а не питоновские кортежи, как у соседних инструментов: здесь переводится
проза с кавычками, тире и апострофами, и одно правило экранирования надёжнее двух.

add не пишет ничего, пока есть хоть одно замечание: колода уже в базе, чинить
её потом дороже, чем переписать партию сейчас.
"""

import io
import json
import os
import re
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОЛОДА = os.path.join(ЗДЕСЬ, "baralho-completo-A1.json")
ПОРЦИЯ = os.path.join(ЗДЕСЬ, "_uk-porcao.json")

# Буквы, которых в украинском алфавите нет вовсе: их появление означает, что кусок
# остался русским. Обратная проверка (є, і, ї, ґ) ничего не доказывает — «банк»
# и «Лісабон» пишутся без них.
РУССКИЕ_БУКВЫ = re.compile("[ыэъё]", re.I)


def читать():
    return json.load(io.open(КОЛОДА, encoding="utf-8"))


def писать(d):
    with io.open(КОЛОДА, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def слов(s):
    return len([x for x in re.split(r"\s+", s.strip()) if x])


def переведена(c):
    return bool((c.get("uk") or "").strip())


def next_(n):
    d = читать()
    ждут = [c for c in d["cards"] if not переведена(c)]
    print("непереведённых: %d из %d" % (len(ждут), len(d["cards"])))
    print("формат: слово | часть речи | перевод | пример | перевод примера | заметка")
    print()
    for i, c in enumerate(ждут[:n], 1):
        print("%3d. %s | %s | %s | %s | %s | %s"
              % (i, c["word"], c.get("pos", ""), c.get("ru", ""),
                 c.get("ex", ""), c.get("exru", ""), c.get("note", "")))


def add():
    d = читать()
    карты = {c["word"]: c for c in d["cards"]}
    порция = json.load(io.open(ПОРЦИЯ, encoding="utf-8"))

    замечания = []
    видели = set()
    for i, p in enumerate(порция, 1):
        сл = (p.get("word") or "").strip()
        uk = (p.get("uk") or "").strip()
        exuk = (p.get("exuk") or "").strip()
        noteuk = (p.get("noteuk") or "").strip()
        где = "%d. %s" % (i, сл or "(без слова)")

        c = карты.get(сл)
        if c is None:
            замечания.append("%s — такого слова в колоде нет" % где)
            continue
        if сл in видели:
            замечания.append("%s — повторяется внутри партии" % где)
            continue
        видели.add(сл)

        if not uk:
            замечания.append("%s — пустой перевод" % где)
        if not exuk:
            замечания.append("%s — пустой перевод примера" % где)
        if c.get("note") and not noteuk:
            замечания.append("%s — заметка есть по-русски, но не по-украински" % где)
        if noteuk and not c.get("note"):
            замечания.append("%s — заметка появилась из ниоткуда" % где)

        for имя, текст in (("перевод", uk), ("пример", exuk), ("заметка", noteuk)):
            м = РУССКИЕ_БУКВЫ.search(текст)
            if м:
                замечания.append("%s — в поле «%s» русская буква «%s»: %s"
                                 % (где, имя, м.group(0), текст))

        # Совпасть с русским может и слово, и даже фраза, но не все три поля разом —
        # это уже не совпадение, а непереведённая карточка.
        if (uk == c.get("ru", "") and exuk == c.get("exru", "")
                and noteuk == (c.get("note") or "")):
            замечания.append("%s — все три поля совпали с русскими" % где)

        разница = abs(слов(exuk) - слов(c.get("exru", "")))
        if разница > 4:
            замечания.append("%s — пример разошёлся с русским на %d слов: «%s» против «%s»"
                             % (где, разница, exuk, c.get("exru", "")))
        if len(noteuk) > 90:
            замечания.append("%s — заметка длиннее 90 символов (%d)" % (где, len(noteuk)))

    if замечания:
        print("партия не влита, замечаний %d:" % len(замечания))
        for з in замечания:
            print("  " + з)
        return 1

    for p in порция:
        c = карты[p["word"].strip()]
        c["uk"] = p["uk"].strip()
        c["exuk"] = p["exuk"].strip()
        c["noteuk"] = (p.get("noteuk") or "").strip()

    писать(d)
    осталось = sum(1 for c in d["cards"] if not переведена(c))
    print("влито карточек: %d, переведено %d из %d, осталось %d"
          % (len(порция), len(d["cards"]) - осталось, len(d["cards"]), осталось))
    return 0


def stat():
    d = читать()
    c = d["cards"]
    есть = sum(1 for x in c if переведена(x))
    print("колода A1: %d карточек" % len(c))
    print("с украинским переводом: %d (%.0f%%)" % (есть, 100.0 * есть / len(c)))
    print("осталось: %d" % (len(c) - есть))
    с_заметкой = sum(1 for x in c if x.get("note"))
    заметок_uk = sum(1 for x in c if (x.get("noteuk") or "").strip())
    print("заметок: %d русских, %d украинских" % (с_заметкой, заметок_uk))


def check():
    d = читать()
    c = d["cards"]
    готовые = [x for x in c if переведена(x)]
    беды = []

    # 1. одинаковый перевод у разных карточек — ловушка режима RU→PT
    видели = {}
    for x in готовые:
        k = x["uk"].strip().lower()
        видели.setdefault(k, []).append(x["word"])
    for k, слова in sorted(видели.items()):
        if len(слова) > 1:
            беды.append("одинаковый перевод «%s»: %s" % (k, ", ".join(слова)))

    # 2. русские буквы
    for x in готовые:
        for имя in ("uk", "exuk", "noteuk"):
            м = РУССКИЕ_БУКВЫ.search(x.get(имя) or "")
            if м:
                беды.append("%s — русская буква «%s» в %s: %s"
                            % (x["word"], м.group(0), имя, x.get(имя)))

    # 3. пустые поля там, где по-русски не пусто
    for x in готовые:
        if not (x.get("exuk") or "").strip():
            беды.append("%s — нет перевода примера" % x["word"])
        if x.get("note") and not (x.get("noteuk") or "").strip():
            беды.append("%s — нет украинской заметки" % x["word"])

    # 4. повторяющиеся примеры
    примеры = {}
    for x in готовые:
        примеры.setdefault((x.get("exuk") or "").strip().lower(), []).append(x["word"])
    for k, слова in sorted(примеры.items()):
        if k and len(слова) > 1:
            беды.append("повторяется пример «%s»: %s" % (k, ", ".join(слова)))

    # 5. заметки длиннее 90
    for x in готовые:
        n = x.get("noteuk") or ""
        if len(n) > 90:
            беды.append("%s — заметка %d символов" % (x["word"], len(n)))

    print("проверено переведённых карточек: %d из %d" % (len(готовые), len(c)))
    if not беды:
        print("замечаний нет")
        return 0
    print("замечаний: %d" % len(беды))
    for б in беды:
        print("  " + б)
    return 1


if __name__ == "__main__":
    цель = sys.argv[1] if len(sys.argv) > 1 else "stat"
    if цель == "next":
        next_(int(sys.argv[2]) if len(sys.argv) > 2 else 50)
    elif цель == "add":
        sys.exit(add())
    elif цель == "check":
        sys.exit(check())
    else:
        stat()
