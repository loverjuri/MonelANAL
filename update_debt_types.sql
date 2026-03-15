-- Обновление debt_kind для существующих долгов по контрагенту
-- Запуск: sqlite3 data/bot.db < update_debt_types.sql
-- Или через Python: python -c "from db.models import engine; from sqlalchemy import text; ..."

-- Яндекс Сплит -> рассрочка
UPDATE debts SET debt_kind = 'installment' 
WHERE counterparty LIKE '%Яндекс сплит%' OR counterparty LIKE '%Yandex%split%';

-- Кредитки -> карта
UPDATE debts SET debt_kind = 'card' 
WHERE counterparty LIKE '%Кредитка%' OR counterparty LIKE '%кредитная карта%' 
   OR counterparty LIKE '%кредитка%';

-- Овердрафт
UPDATE debts SET debt_kind = 'overdraft' 
WHERE counterparty LIKE '%Овердрафт%' OR counterparty LIKE '%овердрафт%';

-- Остальные (Кредит в Сбербанке и т.п.) уже имеют debt_kind='credit' по умолчанию
