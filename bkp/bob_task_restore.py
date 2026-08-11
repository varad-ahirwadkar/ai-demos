#!/usr/bin/env python3
"""
bob_task_restore.py — Restore IBM Bob task history after a version upgrade
==========================================================================
After upgrading Bob, your task history may vanish from the sidebar.
This script writes all legacy tasks from Bob's old JSON task folders
directly into the new SQLite database (~/.bob/db/bob.db) so they
appear in the History panel again.

Root causes fixed:
  1. env IS NULL  — required field Bob's UI needs to render a task
  2. created_at too old — Bob's 14-day cleanup deletes them on startup
  3. is_pinned = 0 — makes tasks eligible for auto-deletion
  4. Messages missing user role — history panel filters out tasks with no user message

Supported platforms: macOS, Linux, Windows
Python 3.8+ required, no extra packages needed.

Usage:
  python3 bob_task_restore.py
  python3 bob_task_restore.py --workspace /path/to/your/project
  python3 bob_task_restore.py --dry-run
"""

import argparse
import json
import os
import platform
import shutil
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path


# ── platform paths ────────────────────────────────────────────────────────────

def get_bob_dir() -> Path:
    """~/.bob on all platforms."""
    return Path.home() / ".bob"


def get_legacy_tasks_dir() -> Path:
    """Old per-task JSON folder created by pre-migration Bob."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "IBM Bob" / \
               "User" / "globalStorage" / "ibm.bob-code" / "tasks"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "IBM Bob" / "User" / "globalStorage" / \
               "ibm.bob-code" / "tasks"
    else:  # Linux
        config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(config) / "IBM Bob" / "User" / "globalStorage" / \
               "ibm.bob-code" / "tasks"


def build_project_id(workspace_path: str) -> str:
    """
    Reconstruct the project_id exactly as Bob's envToWorkspace(formatUri()) does:
      macOS/Linux: file:/abs/path
      Windows:     file:C:\\abs\\path   (drive letter, no leading slash)
    """
    p = str(Path(workspace_path).resolve())
    return f"file:{p}"


# ── helpers ───────────────────────────────────────────────────────────────────

def content_to_str(content) -> str:
    """Flatten Anthropic-style array content or passthrough strings."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or block.get("content") or "")
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return str(content) if content is not None else ""


def get_ui_info(task_path: Path):
    """Return (first_user_message, earliest_timestamp_ms) from ui_messages.json."""
    ui_file = task_path / "ui_messages.json"
    if not ui_file.exists():
        return "", int(time.time() * 1000)
    try:
        msgs = json.loads(ui_file.read_text(encoding="utf-8"))
        text = ""
        for say_type in ("user_feedback", "text"):
            for m in msgs:
                if m.get("type") == "say" and m.get("say") == say_type:
                    t = m.get("text", "")
                    if isinstance(t, str) and t.strip():
                        text = t.strip()[:200]
                        break
            if text:
                break
        return text, int(time.time() * 1000)
    except Exception:
        return "", int(time.time() * 1000)


def make_env(task_id: str, workspace: str, workspace_name: str) -> str:
    """Build the minimal env JSON Bob's UI requires to render a task."""
    system = platform.system()
    plat = {"Darwin": "darwin", "Windows": "win32", "Linux": "linux"}.get(system, "linux")
    shell = "/bin/zsh" if system == "Darwin" else \
            "/bin/bash" if system == "Linux" else "cmd.exe"
    return json.dumps({
        "id": task_id,
        "workspace": workspace,
        "scheme": "file",
        "query": "",
        "workspaceName": workspace_name,
        "language": "en",
        "isPlayground": False,
        "costEffective": True,
        "staticEnvInfo": {
            "primaryWorkspace": workspace,
            "systemInfo": {
                "platform": plat,
                "arch": platform.machine().lower(),
                "shell": shell,
            },
        },
        "modeId": "agent",
    })


# ── main restore ──────────────────────────────────────────────────────────────

def restore(workspace_path: str, dry_run: bool = False) -> None:
    bob_dir      = get_bob_dir()
    db_path      = bob_dir / "db" / "bob.db"
    legacy_dir   = get_legacy_tasks_dir()
    project_id   = build_project_id(workspace_path)
    workspace_name = Path(workspace_path).resolve().name
    NOW          = int(time.time() * 1000)

    # ── pre-flight checks ─────────────────────────────────────────────────────
    if not db_path.exists():
        print(f"❌  Bob DB not found at: {db_path}")
        print("    Open Bob at least once after upgrading so it creates the DB.")
        sys.exit(1)

    if not legacy_dir.exists():
        print(f"❌  Legacy tasks folder not found: {legacy_dir}")
        print("    Nothing to migrate.")
        sys.exit(1)

    old_task_ids = [
        d for d in os.listdir(legacy_dir)
        if (legacy_dir / d).is_dir()
    ]
    if not old_task_ids:
        print("ℹ️  No legacy task folders found. Nothing to do.")
        return

    print(f"📂  Legacy tasks folder : {legacy_dir}  ({len(old_task_ids)} tasks)")
    print(f"🗄️  Bob DB               : {db_path}")
    print(f"🔗  project_id           : {project_id}")
    if dry_run:
        print("🔍  DRY RUN — no changes will be made\n")

    # ── backup ────────────────────────────────────────────────────────────────
    if not dry_run:
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.parent / f"bob.backup.{ts_str}.db"
        shutil.copy2(db_path, backup)
        print(f"✅  Backup created       : {backup}")

    # ── connect & checkpoint WAL ──────────────────────────────────────────────
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    cur = con.cursor()

    # ── collect existing first_messages to detect duplicates ─────────────────
    cur.execute(
        "SELECT first_message FROM tasks WHERE project_id = ?", (project_id,)
    )
    existing_fm = {r[0] for r in cur.fetchall() if r[0]}
    cur.execute(
        "SELECT id FROM tasks WHERE project_id = ?", (project_id,)
    )
    existing_ids = {r[0] for r in cur.fetchall()}

    inserted_tasks = 0
    inserted_msgs  = 0
    skipped        = 0

    for old_id in sorted(old_task_ids):
        task_path = legacy_dir / old_id
        if not task_path.is_dir():
            continue

        # already in DB
        if old_id in existing_ids:
            skipped += 1
            continue

        first_message, _ = get_ui_info(task_path)
        title = first_message[:120] if first_message else f"Task {old_id[:8]}"

        # skip content duplicates
        fm_key = first_message[:120] if first_message else ""
        if fm_key and fm_key in existing_fm:
            skipped += 1
            continue
        if fm_key:
            existing_fm.add(fm_key)

        if dry_run:
            print(f"  [dry-run] would insert: {old_id[:8]}  {title[:60]}")
            inserted_tasks += 1
            continue

        env_json = make_env(old_id, str(Path(workspace_path).resolve()), workspace_name)

        # INSERT with:
        #   created_at = NOW   → avoids 14-day cleanup
        #   is_pinned  = 1     → permanently exempt from auto-delete
        cur.execute(
            """
            INSERT OR IGNORE INTO tasks
              (id, project_id, parent_id, task_type, title, status,
               first_message, directory, env, is_pinned, created_at, updated_at)
            VALUES (?,?,NULL,'normal',?,'paused',?,'',?,1,?,?)
            """,
            (old_id, project_id, title, first_message or title,
             env_json, NOW, NOW),
        )
        if cur.rowcount == 0:
            skipped += 1
            continue
        inserted_tasks += 1

        # Insert messages from api_conversation_history.json
        api_file = task_path / "api_conversation_history.json"
        if api_file.exists():
            try:
                raw = json.loads(api_file.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for i, msg in enumerate(raw):
                        if not isinstance(msg, dict):
                            continue
                        role = msg.get("role") or "user"
                        content_str = content_to_str(msg.get("content", ""))
                        new_data: dict = {
                            "role": role,
                            "content": content_str,
                            "id": str(uuid.uuid4()),
                        }
                        if isinstance(msg.get("_meta"), dict):
                            new_data["_meta"] = msg["_meta"]
                        cur.execute(
                            """
                            INSERT INTO messages (id, task_id, role, data, created_at)
                            VALUES (?,?,?,?,?)
                            """,
                            (str(uuid.uuid4()), old_id, role,
                             json.dumps(new_data), NOW + i),
                        )
                        inserted_msgs += 1
            except Exception as e:
                print(f"  ⚠️  Could not read messages for {old_id[:8]}: {e}")

    if not dry_run:
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.commit()

        # ── summary query ─────────────────────────────────────────────────────
        cur.execute(
            """
            SELECT COUNT(*) FROM tasks t
            WHERE t.project_id = ?
              AND EXISTS (
                SELECT 1 FROM messages m
                WHERE m.task_id = t.id AND m.role = 'user'
              )
            """,
            (project_id,),
        )
        visible = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id = ?", (project_id,)
        )
        total = cur.fetchone()[0]

        print(f"\n✅  Tasks inserted        : {inserted_tasks}")
        print(f"✅  Messages inserted     : {inserted_msgs}")
        print(f"✅  Duplicates skipped    : {skipped}")
        print(f"✅  Total tasks in DB     : {total}")
        print(f"✅  Visible in history    : {visible}")
        print(f"\n👉  Restart Bob — your task history should now appear in the sidebar.")
    else:
        print(f"\n[dry-run] Would insert {inserted_tasks} tasks, skip {skipped}.")

    con.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Restore IBM Bob task history after a version upgrade."
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Path to your workspace/project folder. "
             "Defaults to the current working directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted without modifying the DB.",
    )
    args = parser.parse_args()

    workspace = args.workspace or os.getcwd()
    if not Path(workspace).is_dir():
        print(f"❌  Workspace not found: {workspace}")
        sys.exit(1)

    restore(workspace_path=workspace, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
