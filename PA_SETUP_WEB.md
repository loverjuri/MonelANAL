# Настройка веб-приложения на PythonAnywhere

Для `monocore.pythonanywhere.com` и проекта в `/home/monocore/MonelANAL/`.

## Шаг 1: Virtualenv в Web

1. Вкладка **Web** → ваш сайт
2. В поле **Virtualenv** введите: `/home/monocore/MonelANAL/venv`
3. Если venv ещё нет — создайте (см. шаг 2)

## Шаг 2: Создание venv и установка пакетов

В **Consoles** → **$ Bash** выполните:

```bash
cd /home/monocore/MonelANAL
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Проверка:
```bash
pip list | grep -E "flask|pyotp"
```
Должны быть: flask, flask-login, flask-limiter, flask-caching, pyotp, qrcode.

## Шаг 3: WSGI

**Важно:** строка `import sys` должна быть в самом начале. Без неё будет `NameError: name 'sys' is not defined`.

Файл WSGI (Web → Code → WSGI configuration file) — полностью замените на:

```python
import sys
path = '/home/monocore/MonelANAL'
if path not in sys.path:
    sys.path.insert(0, path)

venv_site = '/home/monocore/MonelANAL/venv/lib/python3.13/site-packages'
if venv_site not in sys.path:
    sys.path.insert(0, venv_site)

from app import application
```

Или скопируйте из файла `WSGI_PA_PASTE.txt` (без комментариев в начале).

## Шаг 4: БД

```bash
cd /home/monocore/MonelANAL
source venv/bin/activate
python run_init.py
python migrate.py
```

## Шаг 5: Веб-пользователь

```bash
python create_web_user.py
```

## Шаг 6: Reload

Web → **Reload** your app.

---

## Если всё ещё ModuleNotFoundError

**1. Проверьте версию Python в venv** — путь `venv/lib/python3.XX/site-packages` должен совпадать с версией в WSGI:
```bash
ls /home/monocore/MonelANAL/venv/lib/
# Если видите python3.10 — в WSGI должно быть python3.10
# Если видите python3.13 — в WSGI должно быть python3.13
```

**2. Проверка пакетов:**
```bash
cd /home/monocore/MonelANAL
source venv/bin/activate
python -c "import pyotp; print('OK')"
```

Если `OK` — пакет есть. Тогда проблема в пути venv_site в WSGI (python3.10 vs python3.13).

**3. Virtualenv в Web:**
- Web → Virtualenv: `/home/monocore/MonelANAL/venv` (зелёная галочка)

## Переменные окружения

Web → по секции внизу: **Environment variables** или в начале WSGI:
```
SECRET_KEY=ваш_секретный_ключ
BOT_USERNAME=ИмяБотаБезСобаки
```

BOT_USERNAME — имя бота для кнопки «Войти через Telegram» (без @). Если не задано, виджет не показывается.

## Привязка Telegram к веб-пользователю

При создании пользователя: `python create_web_user.py` — ответьте «y» на «Link with Telegram (CHAT_ID)?».

Для уже созданного пользователя: `python create_web_user.py --link-telegram`
