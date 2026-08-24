-- Колода «Свои слова» — единственная, у которой нет строк в pt_words.
--
-- Слово, добавленное человеком через экран «Добавить», живёт в его личной строке
-- pt_cards с own = true: содержимое принадлежит ему, а не колоде, и у других
-- его нет. Каталогу такая колода нужна только затем, чтобы её можно было
-- включить и выключить в настройках наравне с остальными.
--
-- Поэтому здесь одна строка в pt_decks и ни одной в pt_words. Клиент знает
-- про этот id: rebuild() показывает свои слова, только если человек подписан
-- на 'manual', а renderDecks() считает их по cards, а не по pt_words.

begin;

insert into public.pt_decks (id, name, descr, level_from, level_to, sort)
values ('manual', 'Свои слова', 'Слова, которые вы добавили сами', '', '', 50)
on conflict (id) do update set name = excluded.name, descr = excluded.descr,
  level_from = excluded.level_from, level_to = excluded.level_to, sort = excluded.sort;

commit;

select id, name, sort,
       (select count(*) from public.pt_words w where w.deck_id = d.id) as слов
  from public.pt_decks d order by sort;
