# AI Settings - Telegram Notes Bot
Project-specific rules. Read `RULES.md` for editing HOW.

## 🚨 Before Code Edits
1. Read `RULES.md`
2. Read relevant sections below
3. Follow Read-Confirm-Replace

## Goal
Telegram bot → saves notes → user's Google Sheet (multi-tenant)

## Tech Stack
```yaml
Python: 3.9+
Bot: aiogram
Sheets: gspread + google-auth
Config: python-dotenv
DB: users.json (migrate to SQLite for prod)
```

## Structure
```
project/
├── RULES.md              # Read before editing
├── AI_Settings.md        # This file
├── main.py               # ⚠️ HIGH-RISK
├── config.py
├── users.json
├── bot/
│   ├── handlers.py      # ⚠️ HIGH-RISK
│   └── utils.py
└── storage/
    ├── base.py
    └── google_sheets.py
```

**High-Risk Files:** `main.py`, `bot/handlers.py`
→ Read entire file before edit, minimal changes, verify syntax

## Google Sheets

**Schema:** `id | telegram_message_id | date_created | content | tags | reply_to_message_id`

**Column constants (use these):**
```python
COLUMN_ID = 0
COLUMN_MESSAGE_ID = 1
COLUMN_DATE = 2
COLUMN_CONTENT = 3
COLUMN_TAGS = 4
COLUMN_REPLY_TO = 5

# Usage:
content = row[COLUMN_CONTENT]  # ✅
# content = row[3]  # ❌ magic number
```

## Registration Flow
1. User: `/start`
2. Bot: "Share sheet with [email], send URL"
3. User: sends URL
4. Bot: extract `spreadsheet_id`, verify access, save to `users.json`

## Code Patterns
```python
# Tags:
tags = [w for w in text.split() if w.startswith('#')]

# ID:
note_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{msg_id}"

# Date:
date = datetime.now().isoformat()

# Sanitize (formula injection):
def sanitize_for_sheets(text):
    if text and text[0] in ('=', '+', '-', '@'):
        return f"'{text}"
    return text

# Rate limit:
user_last_msg = defaultdict(lambda: datetime.min)
if now - user_last_msg[user_id] < timedelta(seconds=3):
    await msg.answer("⏳ Wait 3 sec")
    return
```

## Error Handling
```python
try:
    storage.save_note(data)
except gspread.exceptions.APIError as e:
    logging.error(f"Sheets error: {e}")
    await msg.answer(f"❌ Error: {e}")  # SHOW USER
```

**Rule:** ALWAYS show errors to user (not just log)

## Workflow Protocol
After each step:
```
"Шаг X завершен. Протестируй и подтверди. Готов к следующему?"
```
Wait for confirmation before proceeding.

## Testing Checklist
- [ ] Feature works
- [ ] Errors shown to user
- [ ] No magic numbers
- [ ] Formula injection prevented
- [ ] Rate limiting works
- [ ] No syntax errors in HIGH-RISK files

## CSS (if added later)
```css
:root {
  --primary: #3b82f6;
  --spacing-md: 1rem;
}

/* === Button === */
.button { padding: var(--spacing-md); }
```
Max 2 nesting levels, use BEM-like classes.

## Migration (Post-MVP)
Current: `users.json` (loses data on restart)
Production: SQLite/PostgreSQL with SQLAlchemy

## Common Pitfalls
```python
# ❌ Magic number:
content = row[3]

# ✅ Named constant:
COLUMN_CONTENT = 3
content = row[COLUMN_CONTENT]

# ❌ Silent error:
except: pass

# ✅ Show user:
except Exception as e:
    await msg.answer(f"❌ {e}")

# ❌ Formula injection:
sheet.append_row([msg.text])

# ✅ Sanitized:
sheet.append_row([sanitize_for_sheets(msg.text)])
```

---
**Files:**
- `RULES.md` = HOW to edit
- `AI_Settings.md` = WHAT to build