# -*- coding: utf-8 -*-
"""Расстановка тем у карточек колод B1 и B2.

    python vocabulario/temas.py list         — карточки без темы, порциями
    python vocabulario/temas.py list 120     — следующие 120 без темы
    python vocabulario/temas.py set          — разложить порцию из _temas-porcao.py
    python vocabulario/temas.py stat         — сколько карточек в какой теме

У колод A1 и A2 тема приезжает из temas-A1-A2.json, у B1 и B2 её негде взять:
выгрузка, из которой они написаны, тем не знала. Поэтому тема лежит прямо
в карточке, в поле "tema", и расставляется руками — глазами по слову и переводу,
как и всё остальное в этих колодах.

Порция пишется в vocabulario/_temas-porcao.py (в репозиторий не входит) словарём
ТЕМЫ вида {"a lagoa": "A2", "o desmaio": "B6"}. Ключ — слово ровно как в карточке.
Скрипт ничего не пишет, пока есть хоть одно замечание.
"""
import collections
import importlib.util
import io
import json
import os
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОЛОДЫ = {ур: os.path.join(ЗДЕСЬ, "baralho-completo-%s.json" % ур) for ур in ("B1", "B2")}
ПОРЦИЯ = os.path.join(ЗДЕСЬ, "_temas-porcao.py")

# Темы словника Referencial Camões PLE — те же, что в temas-A1-A2.json и в index.html.
ИМЕНА = {
    "A1": "Бытие", "A2": "Пространство", "A3": "Размер и форма", "A4": "Время",
    "A5": "Количество", "A6": "Качества", "A7": "Оценка", "A8": "Мышление и речь",
    "A9": "Связки и отношения", "B1": "Личные данные", "B2": "Дом и окружение",
    "B3": "Повседневная жизнь", "B4": "Досуг", "B5": "Поездки и транспорт",
    "B6": "Здоровье и гигиена", "B7": "Покупки", "B8": "Еда", "B9": "Услуги",
}


def читать(п):
    return json.load(io.open(п, encoding="utf-8"))


def писать(п, данные):
    io.open(п, "w", encoding="utf-8", newline="").write(
        json.dumps(данные, ensure_ascii=False, indent=1))


def все():
    """[(уровень, карточка)] по обеим колодам, в порядке файлов."""
    out = []
    for ур, п in КОЛОДЫ.items():
        out += [(ур, c) for c in читать(п)["cards"]]
    return out


def без_темы():
    return [(ур, c) for ур, c in все() if not c.get("tema")]


def показать(сколько):
    нет = без_темы()
    print("без темы: %d" % len(нет))
    print("темы: " + ", ".join("%s %s" % (k, v) for k, v in sorted(ИМЕНА.items())))
    print()
    for ур, c in нет[:сколько]:
        print("%s | %s | %s | %s" % (ур, c["word"], c["pos"], c["ru"]))


def разложить():
    spec = importlib.util.spec_from_file_location("porcao", ПОРЦИЯ)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    назначения = m.ТЕМЫ

    по_слову = {}
    for ур, c in все():
        по_слову.setdefault(c["word"], []).append((ур, c))

    замечания = []
    for слово, тема in назначения.items():
        if тема not in ИМЕНА:
            замечания.append("нет такой темы «%s»: %s" % (тема, слово))
        if слово not in по_слову:
            замечания.append("нет такого слова: " + слово)
        elif по_слову[слово][0][1].get("tema"):
            замечания.append("тема уже стоит (%s): %s"
                             % (по_слову[слово][0][1]["tema"], слово))
    if замечания:
        return 0, замечания

    колоды = {ур: читать(п) for ур, п in КОЛОДЫ.items()}
    по_ключу = {(ур, c["word"]): c for ур in колоды for c in колоды[ур]["cards"]}
    сделано = 0
    for слово, тема in назначения.items():
        ур = по_слову[слово][0][0]
        по_ключу[(ур, слово)]["tema"] = тема
        сделано += 1

    for ур, п in КОЛОДЫ.items():
        писать(п, колоды[ур])
    return сделано, []


def статистика():
    счёт = collections.Counter(c.get("tema") or "—" for _, c in все())
    всего = sum(счёт.values())
    for тема, n in sorted(счёт.items()):
        print("%-4s %-22s %4d" % (тема, ИМЕНА.get(тема, "без темы"), n))
    print("%-27s %4d" % ("всего", всего))


if __name__ == "__main__":
    что = sys.argv[1] if len(sys.argv) > 1 else "list"
    if что == "set":
        n, замечания = разложить()
        if замечания:
            print("не записано, замечаний %d:" % len(замечания))
            for з in замечания:
                print("  " + з)
            raise SystemExit(1)
        print("разложено: %d, осталось без темы: %d" % (n, len(без_темы())))
    elif что == "stat":
        статистика()
    else:
        показать(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
