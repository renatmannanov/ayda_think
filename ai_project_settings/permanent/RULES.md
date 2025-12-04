# CODE EDITING RULES
Read before EVERY edit. Non-negotiable.

## Workflow: Read-Confirm-Replace
1. `read_file` exact lines
2. Show user what changes
3. Wait "ок"
4. Edit
5. Verify

## Tools
- `replace_file_content`: 1-5 lines ONLY
- `multi_replace_file_content`: multiple edits
- `write_to_file`: NEVER (unless file completely broken + confirmed)

## Line Deletion - CRITICAL

**WRONG (leaves empty line):**
```python
TargetContent = "  --accent-purple: #8b5cf6;"  # Missing \n
NewContent = ""
# Result: empty line remains
```

**CORRECT (no empty line):**
```python
TargetContent = "  --accent-purple: #8b5cf6;\n"  # Include \n
NewContent = ""
# Result: line removed completely
```

**After deletion:** 
- `read_file` to verify
- If empty line → fix immediately: `TargetContent = "\n"`, `NewContent = ""`

## Common Mistakes

**Whitespace matters:**
```css
File: "  --color: red;"  (2 spaces)
Wrong: "--color: red;"   (0 spaces) ❌
Right: "  --color: red;" (2 spaces) ✅
```

**Line count:**
- Delete 1 line → TargetContent = 1 line + `\n`
- Delete 3 lines → TargetContent = 3 lines

**Capturing too much:**
```python
# Want to delete line 11 only:
10: def process():
11:     # TODO: fix
12:     return data

Wrong: "    # TODO: fix\n    return data\n"  # 2 lines ❌
Right: "    # TODO: fix\n"                    # 1 line ✅
```

## Code Quality

**No magic numbers:**
```python
Wrong: status = row[10]  ❌
Right: COLUMN_STATUS = 10; status = row[COLUMN_STATUS]  ✅
```

**Show errors to users:**
```python
Wrong: except: logging.error(e)  # Silent ❌
Right: except: show_alert(e)     # Visible ✅
```

## Platform Rules

**Windows console:**
```python
Wrong: print("✅")        # Crashes ❌
Right: print("[OK]")      # ASCII ✅
```

**File encoding:**
```python
Right: open('file.txt', 'r', encoding='utf-8')
```

## Verification Checklist
After EVERY edit:
- [ ] Read result (±5 lines)
- [ ] No empty lines if deleted
- [ ] Syntax valid (brackets, indents)
- [ ] Critical files (see AI_Settings) verified

## Token Economics
Read rules + edit: ~800 tokens ✅
Skip rules → fix broken file: ~10,000 tokens ❌

ROI: 12x savings

---
**Quick Delete:**
1. `read_file` → find line
2. Show: "Delete line X: 'content'"
3. Wait "ок"
4. `TargetContent = "content\n"` ← include \n
5. `NewContent = ""`
6. Verify NO empty line