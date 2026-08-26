# -*- coding: utf-8 -*-
"""Украинский перевод карточек колоды: партиями, с проверкой каждой.

Переводится оборот карточки — перевод, перевод примера и заметка. Слово и пример
по-португальски у карточки одни на все языки и не трогаются.

    python vocabulario/uk.py stat          сводка по всем колодам
    python vocabulario/uk.py a2 stat       одна колода подробно
    python vocabulario/uk.py a2 next [N]   показать следующие N непереведённых
    python vocabulario/uk.py a2 add        влить партию из _uk-porcao.json
    python vocabulario/uk.py check         чек-лист качества по всем колодам
    python vocabulario/uk.py a2 check      замечания только по этой колоде

Ключ колоды — первым аргументом, регистр не важен: a2 и A2 одно и то же.
Без ключа работают stat и check — им есть что сказать обо всех колодах разом.

Партия — _uk-porcao.json, список объектов {"word", "uk", "exuk", "noteuk"}.
JSON, а не питоновские кортежи, как у соседних инструментов: здесь переводится
проза с кавычками, тире и апострофами, и одно правило экранирования надёжнее двух.

add не пишет ничего, пока есть хоть одно замечание: колода уже в базе, чинить
её потом дороже, чем переписать партию сейчас. Занятость перевода он проверяет
по всем пяти колодам, а не только по своей: одинаковый перевод у двух карточек —
ловушка режима RU→PT, и границы колоды она не знает.
"""

import io
import json
import os
import re
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КЛЮЧИ = ("a1", "a2", "b1", "b2", "c1")
КОЛОДЫ = {к: os.path.join(ЗДЕСЬ, "baralho-completo-%s.json" % к.upper()) for к in КЛЮЧИ}
ПОРЦИЯ = os.path.join(ЗДЕСЬ, "_uk-porcao.json")

# Буквы, которых в украинском алфавите нет вовсе: их появление означает, что кусок
# остался русским. Обратная проверка (є, і, ї, ґ) ничего не доказывает — «банк»
# и «Лісабон» пишутся без них.
РУССКИЕ_БУКВЫ = re.compile("[ыэъё]", re.I)


def читать(ключ):
    return json.load(io.open(КОЛОДЫ[ключ], encoding="utf-8"))


def писать(ключ, d):
    with io.open(КОЛОДЫ[ключ], "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def все_карточки():
    """Карточки всех колод парами (ключ колоды, карточка)."""
    out = []
    for к in КЛЮЧИ:
        out += [(к, c) for c in читать(к)["cards"]]
    return out


def слов(s):
    return len([x for x in re.split(r"\s+", s.strip()) if x])


def переведена(c):
    return bool((c.get("uk") or "").strip())


def next_(ключ, n):
    d = читать(ключ)
    ждут = [c for c in d["cards"] if not переведена(c)]
    print("колода %s, непереведённых: %d из %d"
          % (ключ.upper(), len(ждут), len(d["cards"])))
    print("формат: слово | часть речи | перевод | пример | перевод примера | заметка")
    print()
    for i, c in enumerate(ждут[:n], 1):
        print("%3d. %s | %s | %s | %s | %s | %s"
              % (i, c["word"], c.get("pos", ""), c.get("ru", ""),
                 c.get("ex", ""), c.get("exru", ""), c.get("note", "")))


def add(ключ):
    d = читать(ключ)
    карты = {c["word"]: c for c in d["cards"]}
    порция = json.load(io.open(ПОРЦИЯ, encoding="utf-8"))
    в_партии = {(p.get("word") or "").strip() for p in порция}

    # Чем уже занят перевод: все колоды сразу. Карточки самой партии из занятого
    # исключаются — иначе при повторном вливании карточка спорила бы сама с собой.
    занято, занято_пример = {}, {}
    for к, c in все_карточки():
        if not переведена(c) or (к == ключ and c["word"] in в_партии):
            continue
        занято.setdefault(c["uk"].strip().lower(), (к, c["word"]))
        пр = (c.get("exuk") or "").strip().lower()
        if пр:
            занято_пример.setdefault(пр, (к, c["word"]))

    замечания = []
    видели = set()
    свои_переводы, свои_примеры = {}, {}
    for i, p in enumerate(порция, 1):
        сл = (p.get("word") or "").strip()
        uk = (p.get("uk") or "").strip()
        exuk = (p.get("exuk") or "").strip()
        noteuk = (p.get("noteuk") or "").strip()
        где = "%d. %s" % (i, сл or "(без слова)")

        c = карты.get(сл)
        if c is None:
            замечания.append("%s — такого слова в колоде %s нет" % (где, ключ.upper()))
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

        for имя_поля, текст in (("перевод", uk), ("пример", exuk), ("заметка", noteuk)):
            м = РУССКИЕ_БУКВЫ.search(текст)
            if м:
                замечания.append("%s — в поле «%s» русская буква «%s»: %s"
                                 % (где, имя_поля, м.group(0), текст))

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

        # Одинаковый перевод у двух карточек — ловушка RU→PT: человек видит одно
        # слово, а правильных ответов два, засчитывается один. Разводим сразу.
        k = uk.lower()
        if k and k in занято:
            чей = занято[k]
            замечания.append("%s — перевод «%s» уже у «%s» (колода %s)"
                             % (где, uk, чей[1], чей[0].upper()))
        elif k and k in свои_переводы:
            замечания.append("%s — перевод «%s» уже у «%s» в этой же партии"
                             % (где, uk, свои_переводы[k]))
        elif k:
            свои_переводы[k] = сл

        kp = exuk.lower()
        if kp and kp in занято_пример:
            чей = занято_пример[kp]
            замечания.append("%s — такой же перевод примера у «%s» (колода %s)"
                             % (где, чей[1], чей[0].upper()))
        elif kp and kp in свои_примеры:
            замечания.append("%s — такой же перевод примера у «%s» в этой же партии"
                             % (где, свои_примеры[kp]))
        elif kp:
            свои_примеры[kp] = сл

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

    писать(ключ, d)
    осталось = sum(1 for c in d["cards"] if not переведена(c))
    print("влито карточек: %d, в колоде %s переведено %d из %d, осталось %d"
          % (len(порция), ключ.upper(),
             len(d["cards"]) - осталось, len(d["cards"]), осталось))
    return 0


def stat(ключ=None):
    if ключ is None:
        всего = готово = 0
        print("колода  карточек  переведено")
        for к in КЛЮЧИ:
            c = читать(к)["cards"]
            есть = sum(1 for x in c if переведена(x))
            всего += len(c)
            готово += есть
            print("%-6s  %8d  %6d (%3.0f%%)"
                  % (к.upper(), len(c), есть, 100.0 * есть / len(c)))
        print("%-6s  %8d  %6d (%3.0f%%)"
              % ("всего", всего, готово, 100.0 * готово / всего))
        print("осталось перевести: %d" % (всего - готово))
        return

    c = читать(ключ)["cards"]
    есть = sum(1 for x in c if переведена(x))
    print("колода %s: %d карточек" % (ключ.upper(), len(c)))
    print("с украинским переводом: %d (%.0f%%)" % (есть, 100.0 * есть / len(c)))
    print("осталось: %d" % (len(c) - есть))
    с_заметкой = sum(1 for x in c if x.get("note"))
    заметок_uk = sum(1 for x in c if (x.get("noteuk") or "").strip())
    print("заметок: %d русских, %d украинских" % (с_заметкой, заметок_uk))


def check(ключ=None):
    """Чек-лист по всем колодам разом.

    Одинаковый перевод ищется по всей базе слов, а не внутри одной колоды: человек
    учит несколько колод сразу, и ловушка RU→PT границы колоды не знает. Ключ
    колоды сужает не поиск, а вывод — спор показывается, если хоть одна из
    спорящих карточек из этой колоды.
    """
    пары = [(к, x) for к, x in все_карточки() if переведена(x)]
    беды = []

    def свои(*кто):
        return ключ is None or ключ in кто

    def имя(к, x):
        return "%s (%s)" % (x["word"], к.upper())

    # 1. одинаковый перевод у разных карточек — ловушка режима RU→PT
    видели = {}
    for к, x in пары:
        видели.setdefault(x["uk"].strip().lower(), []).append((к, x))
    for k, спор in sorted(видели.items()):
        if len(спор) > 1 and свои(*[к for к, _ in спор]):
            беды.append("одинаковый перевод «%s»: %s"
                        % (k, ", ".join(имя(к, x) for к, x in спор)))

    # 2. русские буквы
    for к, x in пары:
        if not свои(к):
            continue
        for поле in ("uk", "exuk", "noteuk"):
            м = РУССКИЕ_БУКВЫ.search(x.get(поле) or "")
            if м:
                беды.append("%s — русская буква «%s» в %s: %s"
                            % (имя(к, x), м.group(0), поле, x.get(поле)))

    # 3. пустые поля там, где по-русски не пусто
    for к, x in пары:
        if not свои(к):
            continue
        if not (x.get("exuk") or "").strip():
            беды.append("%s — нет перевода примера" % имя(к, x))
        if x.get("note") and not (x.get("noteuk") or "").strip():
            беды.append("%s — нет украинской заметки" % имя(к, x))

    # 4. повторяющиеся примеры
    примеры = {}
    for к, x in пары:
        примеры.setdefault((x.get("exuk") or "").strip().lower(), []).append((к, x))
    for k, спор in sorted(примеры.items()):
        if k and len(спор) > 1 and свои(*[к for к, _ in спор]):
            беды.append("повторяется пример «%s»: %s"
                        % (k, ", ".join(имя(к, x) for к, x in спор)))

    # 5. заметки длиннее 90
    for к, x in пары:
        if свои(к) and len(x.get("noteuk") or "") > 90:
            беды.append("%s — заметка %d символов" % (имя(к, x), len(x["noteuk"])))

    охват = ("колоде " + ключ.upper()) if ключ else "всем колодам"
    print("проверено переведённых карточек: %d, замечания по %s" % (len(пары), охват))
    if not беды:
        print("замечаний нет")
        return 0
    print("замечаний: %d" % len(беды))
    for б in беды:
        print("  " + б)
    return 1


if __name__ == "__main__":
    арг = sys.argv[1:]
    ключ = None
    if арг and арг[0].lower() in КОЛОДЫ:
        ключ = арг.pop(0).lower()
    цель = арг[0] if арг else "stat"

    if цель == "next":
        if ключ is None:
            sys.exit("next — про одну колоду: python vocabulario/uk.py a2 next 80")
        next_(ключ, int(арг[1]) if len(арг) > 1 else 50)
    elif цель == "add":
        if ключ is None:
            sys.exit("add — про одну колоду: python vocabulario/uk.py a2 add")
        sys.exit(add(ключ))
    elif цель == "check":
        sys.exit(check(ключ))
    elif цель == "stat":
        stat(ключ)
    else:
        sys.exit("что делать? next, add, stat или check (колоды: %s)" % ", ".join(КЛЮЧИ))
