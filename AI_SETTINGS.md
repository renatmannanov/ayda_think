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

## 8. Development Environment
- **Windows Console:** NEVER use emojis or special Unicode characters in `print()` statements. Use `logging` module or ASCII-only text to avoid `charmap` codec errors.
- **HTML/CSS Integrity:** 
    - NEVER delete the `<head>` section or `<!DOCTYPE html>` declaration.
    - For small files (< 300 lines), PREFER `write_to_file` (rewrite entire file) over `replace_file_content` to avoid accidental deletion of context or breaking structure.
    - ALWAYS verify that critical classes (like `.card`) and tags (`<html>`, `<body>`) exist after editing.

## 9. Project Specific Rules (Added 2024-11-28)
1. **Persistence First**: NEVER rely on local JSON files (`users.json`) for critical data in production environments (Render/Docker). Suggest a Database or persistent volume.
2. **No Magic Numbers**: When accessing Google Sheets columns, ALWAYS use named constants or a mapping dictionary, never hardcoded indices (e.g., `row[10]`).
3. **Error Visibility**: Frontend MUST display API errors to the user (via alert or toast), not just log to console. Silent failures are hard to debug.
4. **Deployment Awareness**: When modifying `api_server.py` or `main.py`, always verify imports and syntax immediately, as these crash the deployment.
5. **CSS Optimization**: Use CSS Variables (`:root`) for colors/spacing. Group styles by component with comment headers. Avoid deep selector nesting (max 2 levels); prefer BEM-like flat classes.
