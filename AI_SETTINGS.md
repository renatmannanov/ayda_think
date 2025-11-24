# AI Settings & Rules

This file contains the persistent configuration, rules, and constraints for the AI agent working on this project. It is updated continuously.

## 1. Project Goals
- **Main Goal:** Create a Telegram bot to save notes to Google Sheets (Multi-Tenant).
- **MVP:** User connects their sheet -> Bot saves notes to THAT sheet.
- **Privacy:** Each user's data is isolated in their own Google Sheet.

## 2. Technology Stack
- **Language:** Python 3.9+
- **Bot Framework:** `aiogram`
- **Sheets Integration:** `gspread` + `google-auth`
- **Config:** `python-dotenv`
- **Database:** `users.json` (Simple JSON file for `user_id: spreadsheet_id` mapping).

## 3. Architecture & Structure
```text
project/
├── .env                 # Secrets (Bot Token, Service Account Path)
├── .gitignore
├── requirements.txt
├── config.py           # Env var loading
├── users.json          # [NEW] User registry
├── storage/
│   ├── __init__.py
│   ├── base.py        # Abstract BaseStorage
│   └── google_sheets.py # Dynamic storage (accepts spreadsheet_id)
├── bot/
│   ├── __init__.py
│   ├── handlers.py    # Registration & Note logic
│   └── utils.py       # [NEW] JSON DB helpers
└── main.py
```

## 4. Implementation Rules
- **Sequential Workflow:** Complete one step, test, ask for user confirmation, then proceed.
- **Complexity:** Minimum. No SQL DBs. Use `users.json`.
- **Registration Flow:**
    1. User sends `/start`.
    2. Bot asks for Google Sheet URL (and gives Service Account Email to share with).
    3. User shares sheet and sends URL.
    4. Bot verifies access and saves `spreadsheet_id` to `users.json`.
- **Code Style:** Readable, commented.
- **Error Handling:** Simple try/except with logging. If access to sheet is lost, notify user.
- **Tags Parsing:** `tags = [word for word in text.split() if word.startswith('#')]`
- **ID Generation:** `f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{message_id}"`
- **Date Format:** ISO (`datetime.now().isoformat()`)

## 5. Google Sheets Schema
Columns: `id | telegram_message_id | date_created | content | tags | reply_to_message_id`

## 6. Interaction Protocol
- **After each step:** Ask: "Шаг X завершен. Протестируй и подтверди, что все работает. Готов к следующему шагу?"
- **Contradictions:** If settings contradict, warn the user and propose solutions.

## 7. Security
- **Formula Injection:** All content starting with `=`, `+`, `-`, `@` MUST be escaped with a leading `'`.
- **Rate Limiting:** Limit user messages to 1 per 3 seconds to prevent API quota exhaustion.
- **Access Control:** Public bot (no allowlist).
