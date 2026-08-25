-- Избранное: личный список слов, собранный руками.
--
-- Полоска фильтров на тренировке умела только то, что задано колодой: уровень,
-- часть речи, тема. Все три признака принадлежат слову, а не человеку, и личную
-- выборку — «эти тридцать слов мне нужны к разговору» — выразить было нечем.
-- fav это чинит: пометка личная, лежит рядом с прогрессом и в pt_words её нет.

alter table public.pt_cards
  add column if not exists fav boolean not null default false;

-- Слияние: пометка — обычный переключатель, обе стороны его ставит человек
-- осознанно, поэтому побеждает свежая правка. То же правило, что у содержимого,
-- и в отличие от archived никакой асимметрии тут не нужно.
create or replace function public.pt_cards_touch() returns trigger
language plpgsql as $$
begin
  if tg_op = 'UPDATE' then

    -- «Выучено» принадлежит человеку. Снять его может только осознанный возврат
    -- в изучение — он проставляет свежий archived_at. Устаревшая копия приходит
    -- с нулём или со старой меткой и выученное не отменяет.
    if old.archived and not new.archived and new.archived_at <= old.archived_at then
      new.archived    := old.archived;
      new.archived_at := old.archived_at;
      new.due         := old.due;
      new.ivl         := old.ivl;
    end if;

    -- Счётчики работы только растут: их нельзя откатить устаревшей копией.
    new.reps   := greatest(coalesce(new.reps,0),   coalesce(old.reps,0));
    new.lapses := greatest(coalesce(new.lapses,0), coalesce(old.lapses,0));

    -- Содержимое, расписание, пометка и надгробие — по версии. Устаревшую версию
    -- не берём, но строку всё равно помечаем изменённой: пусть отправитель заберёт
    -- правду обратно следующей же выборкой, а не останется при своей копии навсегда.
    if new.rev < old.rev then
      new.word    := old.word;
      new.query   := old.query;
      new.pos     := old.pos;
      new.ru      := old.ru;
      new.ex      := old.ex;
      new.exru    := old.exru;
      new.note    := old.note;
      new.level   := old.level;
      new.due     := old.due;
      new.ivl     := old.ivl;
      new.fav     := old.fav;
      new.deleted := old.deleted;
      new.rev     := old.rev;
    end if;

  end if;

  new.updated_at = now();
  return new;
end $$;

notify pgrst, 'reload schema';
