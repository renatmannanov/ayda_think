ЗАДАЧА: Создать Telegram-бота для сохранения заметок в Google Sheets (Multi-tenant)
ЦЕЛЬ MVP: Рабочая связка "пользователь подключил таблицу -> пишет в боте -> сохраняется в ЕГО таблице"
ТЕХНОЛОГИЧЕСКИЙ СТЕК:

Python 3.9+
aiogram
gspread + google-auth для работы с Google Sheets
python-dotenv для управления ключами

АРХИТЕКТУРА:
project/
├── .env                 # TELEGRAM_BOT_TOKEN, GOOGLE_SHEETS_CREDENTIALS
├── .gitignore
├── requirements.txt
├── config.py           # загрузка переменных окружения
├── users.json          # [NEW] БД пользователей: {user_id: spreadsheet_id}
├── storage/
│   ├── __init__.py
│   ├── base.py        # абстрактный класс
│   └── google_sheets.py # логика записи (принимает spreadsheet_id)
├── bot/
│   ├── __init__.py
│   ├── handlers.py    # логика регистрации и сохранения
│   └── utils.py       # [NEW] хелперы для работы с users.json
└── main.py

ПОШАГОВЫЙ ПЛАН РЕАЛИЗАЦИИ:
ШАГ 1: Настройка окружения (Выполнено)

ШАГ 2: Настроить Google Sheets API (Выполнено частично)
Создать Service Account (один на всех).
Включить API.

ШАГ 3: Реализовать storage/base.py

ШАГ 4: Реализовать storage/google_sheets.py
Метод save_note() теперь должен принимать spreadsheet_id динамически.

ШАГ 5: Реализовать управление пользователями (bot/utils.py)
Функции load_users(), save_user(user_id, spreadsheet_id), get_user_spreadsheet(user_id).
Храним в users.json.

ШАГ 6: Реализовать bot/handlers.py
Команда /start: Приветствие, инструкция "Создай таблицу, добавь бота (email), пришли ссылку".
Обработка ссылки на таблицу:
1. Парсим ID таблицы.
2. Проверяем доступ (пробуем прочитать/записать).
3. Если ок -> сохраняем в users.json.
Обработка текста/reply:
1. Проверяем, есть ли user_id в users.json.
2. Если нет -> просим зарегистрироваться.
3. Если есть -> берем spreadsheet_id и сохраняем заметку.

ШАГ 7: Реализовать main.py

ШАГ 8: Тестирование
Два разных пользователя Telegram.
Две разные таблицы.
Проверить, что заметки попадают в правильные таблицы.

ВАЖНЫЕ ПРИНЦИПЫ:
Приватность - каждый пользователь видит только свои данные (в своей таблице).
Обработка ошибок - если бот потерял доступ к таблице, сообщить пользователю.

ПОДСКАЗКИ ПО РЕАЛИЗАЦИИ:
Для парсинга ID таблицы из ссылки используй регулярку.

ДОПОЛНИТЕЛЬНАЯ ЗАДАЧА:
1. создай файл AI_SETTINGS.md
2. запиши туда все настройки, которые получил и сформировал из этого PROMPT'а
3. пополняй и изменяй этот файл постоянно, добавляя новые настройки, которые будут появляться
ЗАДАЧА: Создать Telegram-бота для сохранения заметок в Google Sheets (Multi-tenant)
ЦЕЛЬ MVP: Рабочая связка "пользователь подключил таблицу -> пишет в боте -> сохраняется в ЕГО таблице"
ТЕХНОЛОГИЧЕСКИЙ СТЕК:

## Project Specific Rules (Added 2024-11-28)
1. **Persistence First**: NEVER rely on local JSON files (`users.json`) for critical data in production environments (Render/Docker). Suggest a Database or persistent volume.
2. **No Magic Numbers**: When accessing Google Sheets columns, ALWAYS use named constants or a mapping dictionary, never hardcoded indices (e.g., `row[10]`).
3. **Error Visibility**: Frontend MUST display API errors to the user (via alert or toast), not just log to console. Silent failures are hard to debug.
4. **Deployment Awareness**: When modifying `api_server.py` or `main.py`, always verify imports and syntax immediately, as these crash the deployment.
5. **CSS Optimization**: Use CSS Variables (`:root`) for colors/spacing. Group styles by component with comment headers. Avoid deep selector nesting (max 2 levels); prefer BEM-like flat classes.