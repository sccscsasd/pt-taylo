-- Настройки и счётчик обращений к модели — то, что раньше жило только в панели.
--
-- pt_data, pt_usage и pt_bump_usage были заведены руками в самом начале, когда
-- миграций ещё не писали, и в репозиторий не попали. Это выяснилось 28.10.2026,
-- когда проект Supabase был удалён и базу пришлось поднимать заново: колоды и
-- pt_cards вернулись миграциями, а настройки восстанавливать было нечем.
-- Теперь репозиторий поднимает базу целиком.
--
-- Эта миграция выполняется ПЕРВОЙ на пустом проекте: 001 переносит старые карточки
-- из pt_data, и без таблицы перенос не выполнится. На непустой базе безопасна —
-- всё создаётся через if not exists.

begin;

-- Настройки одного человека одним jsonb: {v:2, settings:{…}}. Когда-то здесь лежала
-- и вся колода, теперь только настройки — колода общая и живёт в pt_words.
create table if not exists public.pt_data (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  data       jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.pt_data enable row level security;

drop policy if exists "pt_data own rows" on public.pt_data;
create policy "pt_data own rows" on public.pt_data
  for all to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Счётчик запросов к модели: строка на человека в сутки. Политик нет намеренно —
-- таблицу трогает только Edge Function своим service-ключом.
create table if not exists public.pt_usage (
  who text not null,
  day date not null default current_date,
  n   integer not null default 0,
  primary key (who, day)
);

alter table public.pt_usage enable row level security;

-- Инкремент и проверка лимита одним вызовом. security definer, потому что у вызывающего
-- прав на таблицу нет вовсе; анониму и вошедшему execute не выдаётся.
create or replace function public.pt_bump_usage(p_ip text, p_limit integer)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  cur integer;
begin
  insert into public.pt_usage (who, day, n)
  values (p_ip, current_date, 1)
  on conflict (who, day) do update set n = public.pt_usage.n + 1
  returning n into cur;
  return cur <= p_limit;
end
$$;

revoke all on function public.pt_bump_usage(text, integer) from public;
revoke all on function public.pt_bump_usage(text, integer) from anon;
revoke all on function public.pt_bump_usage(text, integer) from authenticated;
grant execute on function public.pt_bump_usage(text, integer) to service_role;

commit;

notify pgrst, 'reload schema';
