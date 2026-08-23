-- Слияние правок переезжает на сервер.
--
-- Раньше триггер умел одно: если пришла строка со старым rev — отбросить её целиком
-- и вернуть old. Клиент об этом не узнавал (POST отвечает 200), вычищал карточку
-- из очереди и считал отправленной. А устройство, которое ещё не видело чужих правок,
-- наоборот, затирало их своей копией: телефон без сети принимал слово за невыученное,
-- возвращался в сеть и снимал «выучено», проставленное на ноутбуке.
--
-- Теперь строка не отбрасывается и не принимается целиком, а сливается по полям.
-- Порядок отправки, офлайн и разница в часах перестают что-либо решать.

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

    -- Содержимое, расписание и надгробие — по версии. Устаревшую версию не берём,
    -- но строку всё равно помечаем изменённой: пусть отправитель заберёт правду
    -- обратно следующей же выборкой, а не останется при своей копии навсегда.
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
      new.deleted := old.deleted;
      new.rev     := old.rev;
    end if;

  end if;

  new.updated_at = now();
  return new;
end $$;

-- Откат к прежнему поведению, если понадобится:
-- create or replace function public.pt_cards_touch() returns trigger
-- language plpgsql as $$
-- begin
--   if tg_op = 'UPDATE' and new.rev < old.rev then
--     return old;
--   end if;
--   new.updated_at = now();
--   return new;
-- end $$;
