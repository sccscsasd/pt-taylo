#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Печатает миграцию, заливающую колоду из JSON в общую таблицу pt_words.

Колоды пишутся руками в vocabulario/*.json — это формат авторства, с историей
и разбором правок в git. В базу они попадают миграцией, а не из браузера.

    python vocabulario/deck2sql.py a1 > supabase/migrations/010_deck_a1.sql

Настройки колод — в DECKS ниже. Чтобы добавить колоду: положить рядом её JSON,
дописать сюда запись и выполнить ту же команду.

У колод A1 и A2 уровень и тема берутся из temas-A1-A2.json — слово ищется в списках
a1/a2 каждой темы. Файл общий на обе: колоды делятся по уровню, а темы у них одни.

У колод B1 и B2 файла тем нет, и ключа "temas" в DECKS у них тоже нет: уровень
и тема берутся из самой карточки, из полей level и tema. Тему им расставляет
temas.py — руками, потому что выгрузка тем не знала.

Колода «Свои слова» (id manual) генератором не печатается: слов в pt_words у неё нет,
они лежат у каждого человека в pt_cards. В каталог её заводит миграция 012.
"""

import io
import json
import os
import re
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))

DECKS = {
    "a1": {
        "cards": "baralho-completo-A1.json",
        "temas": "temas-A1-A2.json",
        "name": "Начальный A1",
        "descr": "746 карточек уровня A1 из словника Referencial Camões PLE",
        "level_from": "A1",
        "level_to": "A1",
        "sort": 10,
    },
    "a2": {
        "cards": "baralho-completo-A2.json",
        "temas": "temas-A1-A2.json",
        "name": "Базовый A2",
        "descr": "1127 карточек уровня A2 из словника Referencial Camões PLE",
        "level_from": "A2",
        "level_to": "A2",
        "sort": 20,
    },
    "b1": {
        "cards": "baralho-completo-B1.json",
        "name": "Средний B1",
        "descr": "927 карточек уровня B1 с примерами и заметками",
        "level_from": "B1",
        "level_to": "B1",
        "sort": 30,
    },
    "b2": {
        "cards": "baralho-completo-B2.json",
        "name": "Выше среднего B2",
        "descr": "705 карточек уровня B2 с примерами и заметками",
        "level_from": "B2",
        "level_to": "B2",
        "sort": 40,
    },
    "c1": {
        "cards": "baralho-completo-C1.json",
        "name": "Продвинутый C1",
        "descr": "990 карточек уровня C1: книжный регистр, право, обороты, разговорное",
        "level_from": "C1",
        "level_to": "C1",
        "sort": 50,
    },
}

АРТИКЛЬ = re.compile(r"^(o|a|os|as|um|uma)\s+")
ПУНКТУАЦИЯ = re.compile(r"[.,;:!?\"'()]")


def norm(s):
    """То же, что norm() в index.html и public.pt_norm() в базе."""
    s = (s or "").lower()
    s = АРТИКЛЬ.sub("", s)
    s = ПУНКТУАЦИЯ.sub("", s)
    return s.strip()


def читать(имя):
    with io.open(os.path.join(ЗДЕСЬ, имя), encoding="utf-8") as f:
        return json.load(f)


def лит(s):
    """Строковый литерал для SQL."""
    return "'" + (s or "").replace("'", "''") + "'"


def собрать(ключ):
    d = DECKS[ключ]
    колода = читать(d["cards"])

    # Файл тем есть только у A1–A2. Без него уровень и тема берутся из карточки.
    индекс = {}
    if d.get("temas"):
        темы = читать(d["temas"])
        темы = темы if isinstance(темы, list) else темы["temas"]
        for t in темы:
            for уровень in ("a1", "a2"):
                for слово in t.get(уровень, []):
                    индекс.setdefault(norm(слово), (уровень.upper(), t["id"]))

    выведенные = set(колода.get("retired") or [])
    строки, без_темы, лишние = [], [], []
    видели = set()

    for i, c in enumerate(колода["cards"]):
        слово = (c.get("word") or "").strip()
        if not слово:
            continue
        k = norm(слово)
        if k in выведенные:
            лишние.append(слово)
            continue
        if k in видели:
            лишние.append(слово)
            continue
        видели.add(k)
        уровень, тема = индекс.get(k) or ((c.get("level") or "").upper(), c.get("tema") or "")
        if not тема:
            без_темы.append(слово)
        строки.append((
            "w:" + k, ключ, слово,
            c.get("pos") or "", c.get("ru") or "", c.get("ex") or "",
            c.get("exru") or "", c.get("note") or "", уровень, тема, i,
            c.get("uk") or "", c.get("exuk") or "", c.get("noteuk") or "",
        ))

    return d, строки, без_темы, лишние


def печатать(ключ, кусок=200):
    d, строки, без_темы, лишние = собрать(ключ)

    # Миграция всегда в UTF-8. Через sys.stdout Windows берёт кодировку консоли
    # и спотыкается на первом же португальском â, когда вывод уходит в файл.
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")
    out.write("-- Колода «%s» в общей базе слов. Напечатано vocabulario/deck2sql.py\n" % d["name"])
    out.write("-- Источник: vocabulario/%s%s, карточек: %d.\n"
              % (d["cards"], " + " + d["temas"] if d.get("temas") else "", len(строки)))
    if без_темы:
        out.write("-- Без темы (%d): %s\n"
                  % (len(без_темы), ", ".join(без_темы[:40]) + (" …" if len(без_темы) > 40 else "")))
    out.write("-- Повторное выполнение безопасно: содержимое обновляется, прогресс людей не трогается.\n\n")
    out.write("begin;\n\n")

    out.write(
        "insert into public.pt_decks (id, name, descr, level_from, level_to, sort)\n"
        "values (%s, %s, %s, %s, %s, %d)\n"
        "on conflict (id) do update set name = excluded.name, descr = excluded.descr,\n"
        "  level_from = excluded.level_from, level_to = excluded.level_to, sort = excluded.sort;\n\n"
        % (лит(ключ), лит(d["name"]), лит(d["descr"]),
           лит(d["level_from"]), лит(d["level_to"]), d["sort"])
    )

    # Украинский перевод лежит рядом с русским, тремя колонками: слово и пример
    # по-португальски у карточки одни, меняется только оборот.
    поля = ("(id, deck_id, word, pos, ru, ex, exru, note, level, tema, sort,"
            " uk, exuk, noteuk)")
    обновление = (
        "on conflict (id) do update set deck_id = excluded.deck_id, word = excluded.word,\n"
        "  pos = excluded.pos, ru = excluded.ru, ex = excluded.ex, exru = excluded.exru,\n"
        "  note = excluded.note, level = excluded.level, tema = excluded.tema, sort = excluded.sort,\n"
        "  uk = excluded.uk, exuk = excluded.exuk, noteuk = excluded.noteuk;\n\n"
    )
    for нач in range(0, len(строки), кусок):
        часть = строки[нач:нач + кусок]
        out.write("insert into public.pt_words %s values\n" % поля)
        out.write(",\n".join(
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%d,%s,%s,%s)" % (
                лит(r[0]), лит(r[1]), лит(r[2]), лит(r[3]), лит(r[4]),
                лит(r[5]), лит(r[6]), лит(r[7]), лит(r[8]), лит(r[9]), r[10],
                лит(r[11]), лит(r[12]), лит(r[13]))
            for r in часть
        ))
        out.write("\n" + обновление)

    # Слово, выпавшее из файла колоды, должно исчезнуть и из базы: тогда «вывод слова
    # из колоды» — это просто удаление из JSON, без списка retired и без чистки у людей.
    # now() внутри транзакции — время её начала, и триггер ставит его всем тронутым
    # строкам; у нетронутых метка старее, они и удаляются. Перечислять тысячу id не нужно.
    out.write(
        "delete from public.pt_words\n"
        " where deck_id = %s and updated_at < now();\n\n" % лит(ключ)
    )

    out.write("commit;\n\n")
    out.write(
        "select count(*) as слов, count(*) filter (where level = '') as без_уровня,\n"
        "       count(distinct tema) as тем,\n"
        "       count(*) filter (where uk <> '') as по_украински\n"
        "  from public.pt_words where deck_id = %s;\n" % лит(ключ)
    )

    out.flush()

    sys.stderr.write("колода %s: %d слов, без темы %d, пропущено %d\n"
                     % (ключ, len(строки), len(без_темы), len(лишние)))


if __name__ == "__main__":
    ключ = sys.argv[1] if len(sys.argv) > 1 else "a1"
    if ключ not in DECKS:
        sys.exit("неизвестная колода: %s (есть: %s)" % (ключ, ", ".join(DECKS)))
    печатать(ключ)
