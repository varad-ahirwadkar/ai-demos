# Bob Task History — Migration Guide

If you upgraded IBM Bob and your entire task history disappeared from the sidebar, this guide explains why and how to fix it in under a minute.

---

## What happened

After the upgrade, Bob migrated old per-task JSON files into a new SQLite database (`~/.bob/db/bob.db`). The migration ran, but every legacy task was written with fields that cause the UI to silently ignore them:

| Problem | Effect |
|---|---|
| `env` column is `NULL` | Bob's UI can't render the task — it never appears |
| `created_at` copied from original timestamps | Bob's 14-day startup cleanup deletes them immediately |
| `is_pinned = 0` | Tasks remain eligible for auto-deletion even after the above is fixed |
| Message `content` stored as array (old Anthropic format) | Crashes the UI with `TypeError: t.replace is not a function` when opening a task |

---

## Fix

Run the restore script once, then restart Bob.

### Requirements
- Python 3.8 or later (no extra packages)
- Bob installed and opened at least once after the upgrade (so `~/.bob/db/bob.db` exists)

### Steps

**1. Download the script**

Save [`bob_task_restore.py`](bob_task_restore.py) anywhere on your machine.

**2. Run it from your workspace folder**

```bash
# macOS / Linux
cd /path/to/your/project
python3 bob_task_restore.py

# Windows (PowerShell)
cd C:\path\to\your\project
python bob_task_restore.py
```

Or pass the workspace path explicitly:

```bash
python3 bob_task_restore.py --workspace /path/to/your/project
```

**3. Preview without changing anything**

```bash
python3 bob_task_restore.py --dry-run
```

**4. Restart Bob** — your full task history will appear in the sidebar.

---

## What the script does

1. **Backs up** `~/.bob/db/bob.db` with a timestamp before touching anything
2. **Locates** the legacy task folders:
   - macOS: `~/Library/Application Support/IBM Bob/User/globalStorage/ibm.bob-code/tasks/`
   - Windows: `%APPDATA%\IBM Bob\User\globalStorage\ibm.bob-code\tasks\`
   - Linux: `~/.config/IBM Bob/User/globalStorage/ibm.bob-code/tasks/`
3. **Inserts** each task into the DB with:
   - `env` — properly constructed so the UI can render it
   - `created_at = now` — keeps tasks outside the 14-day cleanup window
   - `is_pinned = 1` — permanently exempt from auto-deletion
   - Messages with content normalised to plain strings (no more crash)
4. **Skips** tasks already in the DB (safe to run multiple times)
5. **Flushes** the WAL journal so Bob reads the changes immediately on next start

---

## Platform notes

| Platform | DB path | Legacy tasks path |
|---|---|---|
| macOS | `~/.bob/db/bob.db` | `~/Library/Application Support/IBM Bob/User/globalStorage/ibm.bob-code/tasks/` |
| Linux | `~/.bob/db/bob.db` | `~/.config/IBM Bob/User/globalStorage/ibm.bob-code/tasks/` |
| Windows | `%USERPROFILE%\.bob\db\bob.db` | `%APPDATA%\IBM Bob\User\globalStorage\ibm.bob-code\tasks\` |

> **Multiple workspaces?** Run the script once per workspace, passing `--workspace` each time.

---

## Troubleshooting

**"Bob DB not found"** — Open Bob at least once after upgrading so it creates the new database, then run the script again.

**"Legacy tasks folder not found"** — Your old tasks may have been in a different location. Check the path above for your OS.

**Tasks appear but crash when opened** — The script normalises old message content. If you still see a crash, your backup is at `~/.bob/db/bob.backup.<timestamp>.db` — copy it back and open an issue.

**Tasks disappear again after a few days** — The script sets `is_pinned = 1` on all restored tasks, which permanently exempts them from the 14-day cleanup. If you ran an older version of this script without the pin, re-run the latest version.
