-- Уровень слова по CEFR. Для словника Camões уровень известен из самих тем
-- (списки a1/a2), поэтому клиент его не хранит; в колонке лежит только то,
-- что вернула модель для слов, добавленных вручную.
alter table public.pt_cards add column if not exists level text not null default '';

notify pgrst, 'reload schema';
