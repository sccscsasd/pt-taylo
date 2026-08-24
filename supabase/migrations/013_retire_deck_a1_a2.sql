-- Колода «Базовый A1–A2» разделена на «Начальный A1» и «Базовый A2».
--
-- Слова уже переехали: миграции 010 и 011 записали те же строки pt_words
-- с deck_id = 'a1' и 'a2'. Ключ строки — 'w:' + pt_norm(word), он от колоды
-- не зависит, поэтому прогресс людей в pt_cards переезд не заметил.
--
-- Остаётся перевести подписки и убрать строку старой колоды из каталога.
-- Выполнять строго после 010 и 011: pt_words.deck_id ссылается на pt_decks
-- с on delete cascade, и удаление 'a1-a2' раньше времени унесло бы слова с собой.

begin;

-- Кто учил A1–A2, тот учит обе половины и свои слова: колода «manual» нужна,
-- иначе после разделения у человека пропали бы собственные карточки.
insert into public.pt_user_decks (user_id, deck_id)
select ud.user_id, d.deck_id
  from public.pt_user_decks ud
  cross join (values ('a1'), ('a2'), ('manual')) as d(deck_id)
 where ud.deck_id = 'a1-a2'
on conflict do nothing;

-- Проверка перед удалением: слов у старой колоды остаться не должно.
do $$
declare осталось int;
begin
  select count(*) into осталось from public.pt_words where deck_id = 'a1-a2';
  if осталось > 0 then
    raise exception 'у колоды a1-a2 осталось % слов — сначала выполните 010 и 011', осталось;
  end if;
end $$;

delete from public.pt_decks where id = 'a1-a2';

commit;

select id, name, level_from, level_to, sort,
       (select count(*) from public.pt_words w where w.deck_id = d.id) as слов,
       (select count(*) from public.pt_user_decks u where u.deck_id = d.id) as подписок
  from public.pt_decks d order by sort;
