-- Починка задвоенных карточек и переход на id, выведенный из слова.
--
-- Что случилось: старый клиент при загрузке готовой колоды выдавал каждой карточке
-- случайный id, свой на каждом устройстве. Колоду загрузили дважды на разных origin,
-- и при первом запуске нового клиента второе устройство отправило на сервер свой набор
-- id — получилась вторая копия тех же 1636 слов. Приложение схлопывает одинаковые слова
-- при получении данных, поэтому дубли не видны, но прогресс разъезжается по двум строкам.
--
-- Резервная копия снята заранее: public.pt_cards_backup_2026_08_22 (4916 строк).
-- Откат: restore из этой таблицы.

-- Нормализация слова ровно как в клиентском norm(): нижний регистр, снять артикль,
-- убрать пунктуацию, обрезать пробелы.
create or replace function public.pt_norm(w text) returns text language sql immutable as $$
  select btrim(regexp_replace(regexp_replace(lower(w), '^(o|a|os|as|um|uma)\s+', ''), '[.,;:!?"''()]', '', 'g'))
$$;

-- 1. Из каждой группы одинаковых слов оставляем строку с наибольшим прогрессом,
--    остальные помечаем надгробием — клиенты уберут их у себя при следующей синхронизации.
--    Физически строки остаются, поэтому шаг обратим.
with ranked as (
  select ctid, row_number() over (
    partition by user_id, public.pt_norm(word)
    order by reps desc, archived desc, due desc, rev desc, id
  ) as rn
  from public.pt_cards
  where not deleted
)
update public.pt_cards c
   set deleted = true, rev = rev + 1
  from ranked r
 where c.ctid = r.ctid and r.rn > 1;

-- 2. id теперь выводится из слова: одно слово — одна строка у пользователя.
--    После этого повторная загрузка колоды идемпотентна на любом устройстве.
update public.pt_cards
   set id = 'w:' || public.pt_norm(word)
 where not deleted
   and id <> 'w:' || public.pt_norm(word);

-- 3. Проверка: строк должно стать столько же, сколько уникальных слов.
select u.email,
       count(*) filter (where not c.deleted)                    as live,
       count(distinct public.pt_norm(c.word)) filter (where not c.deleted) as words,
       count(*) filter (where c.deleted)                        as tombs,
       count(*) filter (where not c.deleted and c.reps > 0)     as studied,
       count(*) filter (where not c.deleted and c.archived)     as learned
  from public.pt_cards c
  join auth.users u on u.id = c.user_id
 group by u.email
 order by u.email;
