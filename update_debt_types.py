"""Обновить debt_kind для существующих долгов по контрагенту.
Запуск: python update_debt_types.py"""
from db.models import engine
from sqlalchemy import text

SQLS = [
    ("Яндекс Сплит -> рассрочка",
     "UPDATE debts SET debt_kind = 'installment' WHERE counterparty LIKE '%Яндекс сплит%' OR counterparty LIKE '%сплит%'"),
    ("Кредитки -> карта",
     "UPDATE debts SET debt_kind = 'card' WHERE counterparty LIKE '%Кредитка%' OR counterparty LIKE '%кредитка%'"),
    ("Овердрафт",
     "UPDATE debts SET debt_kind = 'overdraft' WHERE counterparty LIKE '%Овердрафт%' OR counterparty LIKE '%овердрафт%'"),
]

conn = engine.connect()
for name, sql in SQLS:
    r = conn.execute(text(sql))
    conn.commit()
    print(f"{name}: обновлено {r.rowcount} записей")
conn.close()
print("Готово.")
