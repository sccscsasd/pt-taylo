-- Одно слово — одна строка. Приведение колоды к этому правилу и запрет нарушать его впредь.
--
-- Что было. 23.08.2026 в pt_cards у artem@taylo.co оказалось 5056 строк: 1913 каноничных
-- (id = 'w:' + нормализованное слово) и 3143 со старым видом id — 1560 живых и 1583 надгробия.
-- Живые дубли созданы 22.08 в 13:26 UTC, ещё до перехода на id по слову, а на сервер
-- прилетели одним залпом 23.08 в 13:41 UTC: на одном из устройств осталась открытой
-- вкладка с клиентом до той миграции, и она выплюнула свою очередь. Только тот клиент
-- умеет делать id старого вида — нынешний выводит его из слова.
--
-- Чем это плохо. Клиент схлопывает одинаковые слова при получении и оставляет копию,
-- пришедшую последней. Дубли приходили позже: у 67 выученных карточек нашёлся невыученный
-- двойник, и в приложении было «12 выучено» вместо 78. Прогресс при этом не пропадал —
-- он лежал в каноничной строке, просто заслонённый.
--
-- Почему ограничением, а не сторожем в триггере. Правило «одно слово — одна строка» —
-- это свойство данных, а не поведение клиента. Его место — ограничение в таблице: тогда
-- вторую строку на то же слово не заведёт ни сегодняшний клиент, ни завтрашний,
-- ни забытая вкладка позапрошлой версии.
--
-- Резервная копия снята перед правкой: public.pt_cards_backup_2026_08_23 (6693 строки).

begin;

-- 1. Единственный случай, где каноничная строка стоит надгробием, а живёт дубль
--    (слово «a lagoa»): оживляем каноничную его содержимым, чтобы слово не пропало.
update public.pt_cards w
   set word = d.word, query = d.query, pos = d.pos, ru = d.ru, ex = d.ex, exru = d.exru,
       note = d.note, level = d.level, created = d.created, ivl = d.ivl,
       due         = greatest(w.due, d.due),
       reps        = greatest(w.reps, d.reps),
       lapses      = greatest(w.lapses, d.lapses),
       archived    = (w.archived or d.archived),
       archived_at = greatest(w.archived_at, d.archived_at),
       deleted     = false,
       rev         = greatest(w.rev, d.rev) + 1
  from public.pt_cards d
 where d.user_id = w.user_id
   and not d.deleted and d.id <> 'w:' || public.pt_norm(d.word)
   and w.id = 'w:' || public.pt_norm(d.word) and w.deleted;

-- 2. Прогресс, оставшийся только в дубле (таких карточек четыре, максимум один повтор),
--    переносим в каноничную. Берём лучшее по каждому полю: прогресс принадлежит человеку.
update public.pt_cards w
   set reps        = greatest(w.reps, d.reps),
       lapses      = greatest(w.lapses, d.lapses),
       archived    = (w.archived or d.archived),
       archived_at = greatest(w.archived_at, d.archived_at),
       due         = greatest(w.due, d.due),
       rev         = greatest(w.rev, d.rev) + 1
  from public.pt_cards d
 where d.user_id = w.user_id
   and not d.deleted and d.id <> 'w:' || public.pt_norm(d.word)
   and w.id = 'w:' || public.pt_norm(d.word) and not w.deleted
   and (d.reps > w.reps or (d.archived and not w.archived) or d.due > w.due);

-- 3. Всё неканоничное больше не нужно: и живые дубли, и их надгробия.
delete from public.pt_cards
 where id <> 'w:' || public.pt_norm(word);

-- 4. Поднимаем строки владельца, чтобы устройства забрали правду следующей же выборкой.
--    Данные не меняются — двигается только updated_at, по которой идёт докачка.
update public.pt_cards c
   set rev = c.rev
  from auth.users u
 where u.id = c.user_id and u.email = 'artem@taylo.co';

-- 5. Инвариант: у одного человека не может быть двух живых карточек на одно слово.
--    Надгробия под ограничение не попадают — удалённое слово должно уметь вернуться.
create unique index if not exists pt_cards_one_row_per_word
    on public.pt_cards (user_id, public.pt_norm(word))
 where not deleted;

commit;

-- Проверка. Ожидаем: у artem 1832 живых карточки и 78 выученных, неканоничных нет
-- ни у кого, число разных слов равно числу карточек.
select coalesce(u.email,'—')                                                  as кто,
       count(*) filter (where not c.deleted)                                  as карточек,
       count(*) filter (where c.archived and not c.deleted)                   as выучено,
       count(distinct public.pt_norm(c.word)) filter (where not c.deleted)    as разных_слов,
       count(*) filter (where c.id <> 'w:'||public.pt_norm(c.word))           as неканоничных,
       count(*) filter (where c.deleted)                                      as надгробий
  from public.pt_cards c left join auth.users u on u.id = c.user_id
 group by 1 order by 2 desc;
