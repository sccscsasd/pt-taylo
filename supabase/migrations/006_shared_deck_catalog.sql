-- Общая база слов вместо личных копий колоды.
--
-- Было: колода лежала файлом и копировалась каждому в pt_cards — 1829 строк на человека.
-- Копии расходились (у владельца 1832 слова, у второго пользователя 1637 и 79 давно
-- выведенных), раздача зависела от рукописного DECK_V, а новая колода B1–B2 означала бы
-- ещё по столько же строк каждому.
--
-- Стало: каталог колод и слова — общие, одна строка на слово для всех. В pt_cards
-- остаётся только личное: прогресс и свои слова (own = true). Строка прогресса
-- появляется, когда человек первый раз оценил карточку, а не при раздаче колоды.
--
-- Содержимое колод по-прежнему пишется руками в vocabulario/*.json — это формат
-- авторства, с историей и разбором правок в git. В базу оно попадает миграцией,
-- которую печатает vocabulario/deck2sql.py.

create table if not exists public.pt_decks (
  id         text        primary key,          -- 'a1-a2', 'b1-b2'
  name       text        not null,
  descr      text        not null default '',
  level_from text        not null default '',
  level_to   text        not null default '',
  sort       int         not null default 0,
  published  boolean     not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists public.pt_words (
  id         text        primary key,          -- 'w:' + pt_norm(word), как id карточки у клиента
  deck_id    text        not null references public.pt_decks(id) on delete cascade,
  word       text        not null,
  pos        text        not null default '',
  ru         text        not null default '',
  ex         text        not null default '',
  exru       text        not null default '',
  note       text        not null default '',
  level      text        not null default '',  -- CEFR
  tema       text        not null default '',  -- id темы словника
  sort       int         not null default 0,   -- порядок внутри колоды
  updated_at timestamptz not null default now()
);
create index if not exists pt_words_deck_idx on public.pt_words (deck_id, updated_at);

create table if not exists public.pt_user_decks (
  user_id  uuid        not null references auth.users(id) on delete cascade,
  deck_id  text        not null references public.pt_decks(id) on delete cascade,
  added_at timestamptz not null default now(),
  primary key (user_id, deck_id)
);

-- updated_at ставит сервер: по ней клиент докачивает только изменившиеся слова
create or replace function public.pt_touch_updated() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists pt_decks_touch on public.pt_decks;
create trigger pt_decks_touch before insert or update on public.pt_decks
  for each row execute function public.pt_touch_updated();

drop trigger if exists pt_words_touch on public.pt_words;
create trigger pt_words_touch before insert or update on public.pt_words
  for each row execute function public.pt_touch_updated();

-- Каталог читают все вошедшие. Политик на запись нет намеренно: колоду меняет
-- миграция, а не приложение, — тогда её нельзя испортить из браузера.
alter table public.pt_decks      enable row level security;
alter table public.pt_words      enable row level security;
alter table public.pt_user_decks enable row level security;

drop policy if exists "pt_decks read" on public.pt_decks;
create policy "pt_decks read" on public.pt_decks
  for select to authenticated using (true);

drop policy if exists "pt_words read" on public.pt_words;
create policy "pt_words read" on public.pt_words
  for select to authenticated using (true);

-- Свои колоды человек выбирает сам, чужие подписки ему не видны.
drop policy if exists "pt_user_decks own" on public.pt_user_decks;
create policy "pt_user_decks own" on public.pt_user_decks
  for all to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Своё слово: содержимое лежит в самой строке pt_cards, слова колод его не заполняют.
alter table public.pt_cards add column if not exists own boolean not null default false;

notify pgrst, 'reload schema';
