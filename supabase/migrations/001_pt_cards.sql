-- Карточки построчно: одна строка = одна карточка одного пользователя.
-- До этого вся колода лежала одним jsonb в pt_data, поэтому любая оценка
-- в тренировке гнала на сервер весь снимок, а удаления возвращались с других устройств.

create table if not exists public.pt_cards (
  user_id     uuid        not null references auth.users(id) on delete cascade,
  id          text        not null,
  word        text        not null,
  query       text        not null default '',
  pos         text        not null default '',
  ru          text        not null default '',
  ex          text        not null default '',
  exru        text        not null default '',
  note        text        not null default '',
  created     bigint      not null default 0,
  due         bigint      not null default 0,
  ivl         integer     not null default 0,   -- interval — зарезервированное слово, поэтому ivl
  reps        integer     not null default 0,
  lapses      integer     not null default 0,
  archived    boolean     not null default false,
  archived_at bigint      not null default 0,
  deleted     boolean     not null default false, -- надгробие: чтобы удаление доехало до других устройств
  rev         bigint      not null default 0,     -- версия правки по часам клиента
  updated_at  timestamptz not null default now(), -- ставит сервер, по ней клиент докачивает изменения
  primary key (user_id, id)
);

create index if not exists pt_cards_sync_idx on public.pt_cards (user_id, updated_at);

create or replace function public.pt_cards_touch() returns trigger
language plpgsql as $$
begin
  if tg_op = 'UPDATE' and new.rev < old.rev then
    return old;                     -- пришла устаревшая версия: строку не трогаем
  end if;
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists pt_cards_touch on public.pt_cards;
create trigger pt_cards_touch before insert or update on public.pt_cards
  for each row execute function public.pt_cards_touch();

alter table public.pt_cards enable row level security;
drop policy if exists "pt_cards own rows" on public.pt_cards;
create policy "pt_cards own rows" on public.pt_cards
  for all to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Перенос того, что уже накоплено в pt_data.data->'cards'.
insert into public.pt_cards
  (user_id,id,word,query,pos,ru,ex,exru,note,created,due,ivl,reps,lapses,archived,archived_at,rev)
select d.user_id,
       coalesce(nullif(c->>'id',''), md5(d.user_id::text || (c->>'word'))),
       c->>'word',
       coalesce(c->>'query',''),
       coalesce(c->>'pos',''),
       coalesce(c->>'ru',''),
       coalesce(c->>'ex',''),
       coalesce(c->>'exru',''),
       coalesce(c->>'note',''),
       coalesce((c->>'created')::bigint,0),
       coalesce((c->>'due')::bigint,0),
       coalesce((c->>'interval')::numeric::int,0),
       coalesce((c->>'reps')::numeric::int,0),
       coalesce((c->>'lapses')::numeric::int,0),
       coalesce((c->>'archived')::boolean,false),
       coalesce((c->>'archivedAt')::bigint,0),
       coalesce((c->>'created')::bigint,0)
from public.pt_data d, jsonb_array_elements(d.data->'cards') c
where jsonb_typeof(d.data->'cards') = 'array'
  and coalesce(c->>'word','') <> ''
on conflict (user_id,id) do nothing;

notify pgrst, 'reload schema';
