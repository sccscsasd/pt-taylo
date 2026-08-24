# -*- coding: utf-8 -*-
"""Закрытие пропусков в колодах: карточка кладётся в колоду по своему уровню.

    python vocabulario/lacunas.py check   — тематическая сверка: чего нет ни в одной колоде
    python vocabulario/lacunas.py add     — добавить порцию из _lacunas-porcao.py

Выгрузка B1–B2 на 3000 слов оказалась дырявой ровно так же, как словник Camões:
в ней есть telecinesia и afasia, но нет atingir, contrato, greve, conselho, medo.
Пропуски находятся тематической сверкой (`check`), а не частотным списком — список
тем лежит в `temas-verificacao.json` рядом.

Порция пишется в `vocabulario/_lacunas-porcao.py` (в репозиторий не входит) списком
кортежей КАРТОЧКИ вида (слово, часть речи, уровень, тема, перевод, пример, перевод
примера, заметка). Уровень решает, в какую колоду ляжет карточка:

  A1, A2 → baralho-completo-A1-A2.json, и слово дописывается в temas-A1-A2.json
           в список a1/a2 своей темы: у колоды A1–A2 генератор берёт уровень и тему
           только оттуда, иначе слово уедет в базу пустым;
  B1     → baralho-completo-B1.json;
  B2     → baralho-completo-B2.json. Файла тем у этих двух колод нет, уровень и тему
           генератор берёт из самой карточки.

В отличие от b1b2-passo.py, `add` ничего не пишет, пока есть хоть одно замечание:
колода A1–A2 уже залита в базу, чинить её потом дороже.
"""
import io
import importlib.util
import json
import os
import re
import sys

БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ЗДЕСЬ = os.path.join(БАЗА, "vocabulario")
КОЛОДА_A = os.path.join(ЗДЕСЬ, "baralho-completo-A1-A2.json")
КОЛОДЫ_B = {"B1": os.path.join(ЗДЕСЬ, "baralho-completo-B1.json"),
            "B2": os.path.join(ЗДЕСЬ, "baralho-completo-B2.json")}
ТЕМЫ_A = os.path.join(ЗДЕСЬ, "temas-A1-A2.json")
СВЕРКА = os.path.join(ЗДЕСЬ, "temas-verificacao.json")
ПОРЦИЯ = os.path.join(ЗДЕСЬ, "_lacunas-porcao.py")

АРТИКЛЬ = re.compile(r"^(o|a|os|as|um|uma)\s+")
ПУНКТУАЦИЯ = re.compile(r"[.,;:!?\"'()]")


def norm(s):
    """То же, что norm() в index.html и public.pt_norm() в базе."""
    s = (s or "").lower()
    return ПУНКТУАЦИЯ.sub("", АРТИКЛЬ.sub("", s)).strip()


def читать(п):
    return json.load(io.open(п, encoding="utf-8"))


def писать(п, данные):
    io.open(п, "w", encoding="utf-8", newline="").write(
        json.dumps(данные, ensure_ascii=False, indent=1))


def все_колоды():
    карточки = читать(КОЛОДА_A)["cards"]
    for п in КОЛОДЫ_B.values():
        карточки += читать(п)["cards"]
    return карточки


def сверить():
    """Печатает, каких слов из списка сверки нет ни в одной колоде."""
    слова = [c["word"].lower() for c in все_колоды()]
    точно = {norm(s) for s in слова}

    def есть(w):
        # слово может лежать внутри словосочетания: «paragem» в «a paragem de autocarro»
        return norm(w) in точно or any(
            re.search(r"\b" + re.escape(w) + r"\b", s) for s in слова)

    всего = 0
    for тема in читать(СВЕРКА):
        все = list(dict.fromkeys(тема["palavras"]))
        нет = [w for w in все if not есть(w)]
        всего += len(нет)
        print("\n%s %s — нет %d из %d:" % (тема["id"], тема["ru"], len(нет), len(все)))
        if нет:
            print("  " + ", ".join(нет))
    print("\nВСЕГО ПРОПУСКОВ: %d" % всего)


def проверить(порция, карточки):
    """Замечания по порции. Пусто — можно писать."""
    было = {norm(c["word"]) for c in карточки}
    переводы = {}
    примеры = {}
    for c in карточки:
        переводы.setdefault(c["ru"], []).append(c["word"])
        примеры.setdefault(c["ex"], []).append(c["word"])
    замечания = []
    for w, pos, lvl, tema, ru, ex, exru, note in порция:
        k = norm(w)
        if k in было:
            замечания.append("уже есть: " + w)
        было.add(k)
        if lvl not in ("A1", "A2", "B1", "B2"):
            замечания.append("непонятный уровень «%s»: %s" % (lvl, w))
        if ru in переводы:
            замечания.append("одинаковый перевод «%s»: %s и %s" % (ru, переводы[ru][0], w))
        переводы.setdefault(ru, []).append(w)
        if ex in примеры:
            замечания.append("пример повторяет карточку %s: %s" % (примеры[ex][0], w))
        примеры.setdefault(ex, []).append(w)
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

    замечания = проверить(порция, все_колоды())
    if замечания:
        return 0, 0, замечания

    a = читать(КОЛОДА_A)
    b = {ур: читать(п) for ур, п in КОЛОДЫ_B.items()}
    темы = читать(ТЕМЫ_A)
    по_id = {t["id"]: t for t in темы}
    в_a, в_b = 0, 0

    for w, pos, lvl, tema, ru, ex, exru, note in порция:
        карточка = {"word": w, "pos": pos, "level": lvl, "ru": ru,
                    "ex": ex, "exru": exru, "note": note}
        if lvl in ("A1", "A2"):
            if tema not in по_id:
                return 0, 0, ["нет такой темы: %s (%s)" % (tema, w)]
            a["cards"].append(карточка)
            # в файле тем слова лежат без артикля: «chuva», а не «a chuva»
            по_id[tema].setdefault(lvl.lower(), []).append(АРТИКЛЬ.sub("", w))
            в_a += 1
        else:
            карточка["tema"] = tema
            b[lvl]["cards"].append(карточка)
            в_b += 1

    писать(КОЛОДА_A, a)
    for ур, п in КОЛОДЫ_B.items():
        писать(п, b[ур])
    писать(ТЕМЫ_A, темы)
    return в_a, в_b, []


if __name__ == "__main__":
    что = sys.argv[1] if len(sys.argv) > 1 else "check"
    if что == "add":
        в_a, в_b, замечания = добавить()
        if замечания:
            print("не записано, замечаний %d:" % len(замечания))
            for з in замечания:
                print("  " + з)
            raise SystemExit(1)
        print("добавлено: в A1–A2 %d, в B1 и B2 %d" % (в_a, в_b))
        print("теперь в колодах: A1–A2 %d, B1 %d, B2 %d"
              % (len(читать(КОЛОДА_A)["cards"]),
                 len(читать(КОЛОДЫ_B["B1"])["cards"]),
                 len(читать(КОЛОДЫ_B["B2"])["cards"])))
    else:
        сверить()
