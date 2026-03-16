# Инструкция по деплою MonelANAL на PythonAnywhere (free)

Telegram-бот для учёта ЗП и финансов. Работает на бесплатном плане PythonAnywhere с внешним cron для расписания.

## Ограничения free-плана

- **100 CPU seconds/day** — достаточно для webhook и cron-запросов
- **512 MB диск** — SQLite и код занимают мало места
- **Web app истекает через 1 месяц** — нужно продлевать вручную (см. раздел ниже)
- **Нет scheduled tasks** — используем cron-job.org
- **api.telegram.org** — в whitelist, работает

---

## 1. Регистрация и создание Web App

1. Зарегистрируйтесь на [pythonanywhere.com](https://www.pythonanywhere.com)
2. Вкладка **Web** → **Add a new web app**
3. Выберите **Flask**, Python 3.10
4. Укажите путь к проекту: `/home/USERNAME/monelanal` (где USERNAME — ваш логин)

---

## 2. Загрузка кода

### Вариант A: через Git

```bash
cd ~
git clone https://github.com/YOUR_REPO/monelanal.git
# или скопируйте папку monelanal в ~/monelanal
```

### Вариант B: вручную

1. Вкладка **Files** → создайте папку `monelanal`
2. Загрузите все файлы из папки `monelanal` проекта

Структура должна быть:

```
/home/USERNAME/monelanal/
├── app.py
├── config.py
├── wsgi.py
├── run_init.py
├── set_webhook.py
├── requirements.txt
├── bot/
├── db/
├── services/
└── data/          ← создастся при init
```

---

## 3. Виртуальное окружение и зависимости

1. Вкладка **Consoles** → **$ Bash**
2. Создайте venv и установите пакеты:

```bash
cd ~/monelanal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Важно:** В WSGI настройте путь к `venv` (см. раздел 4). Без этого приложение будет использовать системный Python без ваших пакетов (ошибка `ModuleNotFoundError`).

---

## 4. Настройка WSGI

1. Вкладка **Web** → **Code** → **WSGI configuration file**
2. Замените содержимое на:

```python
import sys
path = '/home/USERNAME/monelanal'
if path not in sys.path:
    sys.path.insert(0, path)

# Use venv packages (adjust python3.10 if your Python version differs)
venv_site = '/home/USERNAME/monelanal/venv/lib/python3.10/site-packages'
if venv_site not in sys.path:
    sys.path.insert(0, venv_site)

from app import application
```

Подставьте **USERNAME** на свой логин.

---

## 5. Переменные окружения

### Вариант A: Environment variables (если доступны)

Вкладка **Web** → прокрутите вниз до раздела **Environment variables** → добавьте `BOT_TOKEN`, `CHAT_ID`, `CRON_SECRET`.

### Вариант B: через WSGI (если Environment variables нет)

Если раздела Environment variables нет (например, на free), добавьте переменные **в начало** WSGI-файла:

```python
import os
os.environ["BOT_TOKEN"] = "ВСТАВЬТЕ_ТОКЕН_ОТ_BOTFATHER"
os.environ["CHAT_ID"] = "ВСТАВЬТЕ_ВАШ_CHAT_ID"
os.environ["CRON_SECRET"] = "придумайте_секретную_строку"

import sys
path = '/home/USERNAME/monelanal'
# ... остальной код
```

| Ключ        | Значение                                           |
|-------------|----------------------------------------------------|
| BOT_TOKEN   | Токен от @BotFather                                |
| CHAT_ID     | Ваш Telegram Chat ID (от @userinfobot)            |
| CRON_SECRET | Секретный токен для cron (придумайте строку)      |
| SECRET_KEY  | Секрет для сессий веб-приложения                  |
| RECAPTCHA_SITE_KEY | reCAPTCHA v3 site key (опционально)        |
| RECAPTCHA_SECRET_KEY | reCAPTCHA v3 secret key (опционально)     |

---

## 5a. Добавление записей за прошлые дни

Если нужно вручную добавить рабочие дни (например, 11 и 12 число):

```bash
cd ~/monelanal
source venv/bin/activate
# 11 и 12 число текущего месяца (по 8 ч):
python add_past_days.py

# Или указать даты явно:
python add_past_days.py 2025-03-11 2025-03-12
```

---

## 6. Инициализация БД и календаря

В консоли (Bash):

```bash
cd ~/monelanal
source venv/bin/activate
python run_init.py
```

---

## 6a. Миграции и инициализация

**Первая настройка:** если БД пустая или новая, сначала запустите:

```bash
cd ~/monelanal
source venv/bin/activate
python run_init.py   # создаёт все таблицы
python migrate.py   # добавляет новые колонки и таблицы
```

**После обновления кода (git pull):**

```bash
pip install -r requirements.txt
python migrate.py
```

Без этого возможны ошибки `no such table: logs`, `no such column: finance.exclude_from_budget` и т.п.

---

## 6b. Веб-приложение (опционально)

Веб-версия доступна по адресу `https://USERNAME.pythonanywhere.com/web/` с логином и паролем.

1. **Создать пользователя** (один раз):
   ```bash
   python create_web_user.py
   # Введите логин, пароль. Отсканируйте QR-код в Google Authenticator.
   ```

2. **Переменные окружения**: добавьте `SECRET_KEY`. Для капчи (защита от брутфорса) — `RECAPTCHA_SITE_KEY` и `RECAPTCHA_SECRET_KEY` с [Google reCAPTCHA v3](https://www.google.com/recaptcha/admin).

3. **Статика**: в PA Web укажите путь к статике `/web/static/` для экономии CPU.

---

## 7. Установка webhook

```bash
export BOT_TOKEN="ваш_токен"
export WEBHOOK_URL="https://USERNAME.pythonanywhere.com/webhook"
python set_webhook.py set
```

Проверка: `python set_webhook.py check`

---

## 8. Настройка cron (cron-job.org)

1. Зарегистрируйтесь на [cron-job.org](https://cron-job.org)
2. Создайте задания по таблице (время — MSK, если cron-job в UTC — сдвиньте на -3 часа):

| Задача             | Расписание          | URL                                                  |
|--------------------|---------------------|------------------------------------------------------|
| main-work          | 18:00 MSK ежедневно | `https://USERNAME.pythonanywhere.com/cron/main-work?token=CRON_SECRET` |
| second-job         | 00:05 MSK ежедневно | `.../cron/second-job?token=CRON_SECRET`              |
| payday             | 10:00 MSK 10 и 25   | `.../cron/payday?token=CRON_SECRET`                  |
| reminder-main      | 19:00 MSK ежедневно | `.../cron/reminder-main?token=CRON_SECRET`           |
| reminder-second    | 00:30 MSK ежедневно | `.../cron/reminder-second?token=CRON_SECRET`          |
| prod-calendar      | 01:00 1-го числа    | `.../cron/prod-calendar?token=CRON_SECRET`           |
| subscriptions      | 09:00 MSK ежедневно | `.../cron/subscriptions?token=CRON_SECRET`            |
| overspend-digest   | 20:00 MSK ежедневно | `.../cron/overspend-digest?token=CRON_SECRET`        |
| debt-reminders     | 09:30 MSK ежедневно | `.../cron/debt-reminders?token=CRON_SECRET`          |
| goal-deadline      | 10:00 MSK 1-го числа| `.../cron/goal-deadline?token=CRON_SECRET`           |
| backup             | 03:00 MSK ежедневно | `.../cron/backup?token=CRON_SECRET`                  |
| auto-subscriptions | 08:00 MSK ежедневно | `.../cron/auto-subscriptions?token=CRON_SECRET`      |
| cleanup-logs       | 04:00 MSK воскресенье| `.../cron/cleanup-logs?token=CRON_SECRET`           |

Для payday можно использовать два отдельных задания: одно на 10-е, другое на 25-е.

---

## 9. Перезапуск Web App

Вкладка **Web** → кнопка **Reload** у вашего приложения.

---

## 10. Продление Web App (раз в месяц)

На free-плане Web App истекает через 1 месяц. При истечении:

1. Вкладка **Web**
2. Нажмите **Extend** или **Renew** у истёкшего приложения (если доступно)
3. Либо создайте приложение заново и заново укажите WSGI, путь, переменные

Рекомендуется поставить себе напоминание в календаре.

---

## Команды бота

| Команда / кнопка | Действие                                              |
|------------------|--------------------------------------------------------|
| /start, /help    | Главное меню                                          |
| Статус           | ЗП, баланс, долги, дата выплаты                       |
| Расход           | Записать расход (сумма → категория → комментарий)     |
| /расход 500 еда  | Быстрый расход (сумма + категория одной строкой)      |
| Доход            | Записать внезарплатный доход                          |
| Бюджет           | План, лимиты, прогноз, 50/30/20, предложение плана   |
| Цели             | Накопления (типы, авто-пополнение, архив, темп)       |
| Долги            | Учёт долгов и кредитов, погашение, история            |
| Подписки         | Регулярные платежи, авто-списание, просроченные       |
| Аналитика        | Отчёты за период, графики, топ, сравнение, среднее    |
| История          | Просмотр операций за день/неделю/месяц                |
| Шаблоны          | Быстрые расходы по шаблонам                           |
| Настройки        | Тихие часы, пороги, экспорт, удаление данных          |
| /редактировать   | Изменить/удалить последний расход                     |

**Автоматические функции (через cron):**
- Ежедневный дайджест с рекомендациями и советами
- Напоминания о подписках и долгах
- Авто-списание подписок с флагом auto_create_expense
- Авто-пополнение целей при зарплате
- Ежедневный бэкап данных
- Напоминания о приближающихся дедлайнах целей
- Геймификация: достижения за streak и экономию
- Ротация старых логов

---

## Изменение конфигурации

Параметры (FixedSalary, PayDay1, PayDay2 и т.д.) хранятся в таблице `config`. Для редактирования:

```bash
cd ~/monelanal
source venv/bin/activate
python -c "
from db.repositories import get_session, set_config_param
s = get_session()
set_config_param(s, 'FixedSalary', '120000')
set_config_param(s, 'ChatID', '123456789')
s.close()
"
```

---

## Миграция данных из Google Sheets (опционально)

Если нужно перенести данные из старой Google Таблицы, создайте скрипт, который экспортирует CSV и импортирует в SQLite. Структура таблиц описана в `db/models.py`.

---

## Проверка работы

1. Откройте `https://USERNAME.pythonanywhere.com/` — должно быть «OK»
2. Напишите боту в Telegram — должен ответить меню
3. Проверьте логи: вкладка **Web** → **Log files**
