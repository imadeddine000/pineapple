"""
Pineapple database layer — SQLite-backed persistence for repos, detections, dockerfiles, builds.
"""

import sqlite3
import uuid
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DB_DIR = Path.home() / ".pineapple"
DB_PATH = DB_DIR / "dashboard.db"


def _get_db() -> sqlite3.Connection:
    """Get a database connection, creating schema if needed."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repos (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            name TEXT NOT NULL,
            local_path TEXT,
            clone_status TEXT DEFAULT 'pending',
            clone_progress REAL DEFAULT 0,
            clone_log TEXT DEFAULT '',
            clone_error TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS detections (
            id TEXT PRIMARY KEY,
            repo_id TEXT REFERENCES repos(id) ON DELETE CASCADE,
            framework TEXT, type TEXT, language TEXT,
            port INTEGER, package_manager TEXT,
            build_command TEXT, install_command TEXT, start_command TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS dockerfiles (
            id TEXT PRIMARY KEY,
            repo_id TEXT REFERENCES repos(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            lines INTEGER, size INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS builds (
            id TEXT PRIMARY KEY,
            repo_id TEXT REFERENCES repos(id) ON DELETE CASCADE,
            tag TEXT, status TEXT DEFAULT 'pending',
            success INTEGER, log TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS github_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            github_login TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS github_accounts (
            id TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            account_type TEXT DEFAULT 'user',
            installation_id TEXT,
            access_token TEXT,
            token_expires_at REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            repo_id TEXT REFERENCES repos(id) ON DELETE SET NULL,
            gitignore TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_repos_url ON repos(url);
        CREATE INDEX IF NOT EXISTS idx_repos_status ON repos(clone_status);
    """)
    conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


# ── Repo operations ──

def create_repo(url: str, name: str) -> dict:
    conn = _get_db()
    try:
        repo_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO repos (id, url, name, clone_status) VALUES (?, ?, ?, ?)",
            (repo_id, url, name, 'pending'),
        )
        conn.commit()
        return get_repo(repo_id)
    finally:
        conn.close()


def get_repo(repo_id: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_repos() -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM repos ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_repo_clone(repo_id: str, status: str, progress: float = 0,
                       log: str = "", error: str | None = None) -> None:
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE repos SET clone_status=?, clone_progress=?, clone_log=?,"
            " clone_error=?, updated_at=datetime('now') WHERE id=?",
            (status, progress, log[-10000:], error, repo_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_repo_path(repo_id: str, local_path: str) -> None:
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE repos SET local_path=?, updated_at=datetime('now') WHERE id=?",
            (local_path, repo_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_repo(repo_id: str) -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
        conn.commit()
    finally:
        conn.close()


# ── Detection operations ──

def save_detection(repo_id: str, detection: dict) -> dict:
    conn = _get_db()
    try:
        # Delete old detection for this repo
        conn.execute("DELETE FROM detections WHERE repo_id = ?", (repo_id,))
        det_id = uuid.uuid4().hex[:12]
        conn.execute(
            """INSERT INTO detections
               (id, repo_id, framework, type, language, port, package_manager,
                build_command, install_command, start_command)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (det_id, repo_id,
             detection.get('framework'),
             detection.get('type'),
             detection.get('language'),
             detection.get('port'),
             detection.get('package_manager'),
             detection.get('build_command'),
             detection.get('install_command'),
             detection.get('start_command')),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM detections WHERE id = ?", (det_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_detection(repo_id: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM detections WHERE repo_id = ? ORDER BY created_at DESC LIMIT 1",
            (repo_id,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


# ── Dockerfile operations ──

def save_dockerfile(repo_id: str, content: str) -> dict:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM dockerfiles WHERE repo_id = ?", (repo_id,))
        df_id = uuid.uuid4().hex[:12]
        lines = content.count('\n') + 1
        conn.execute(
            "INSERT INTO dockerfiles (id, repo_id, content, lines, size)"
            " VALUES (?, ?, ?, ?, ?)",
            (df_id, repo_id, content, lines, len(content)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM dockerfiles WHERE id = ?", (df_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_dockerfile(repo_id: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM dockerfiles WHERE repo_id = ? ORDER BY created_at DESC LIMIT 1",
            (repo_id,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


# ── Build operations ──

def create_build(repo_id: str, tag: str) -> dict:
    conn = _get_db()
    try:
        build_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO builds (id, repo_id, tag) VALUES (?, ?, ?)",
            (build_id, repo_id, tag),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_build(build_id: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_build(build_id: str, status: str, log: str = "",
                  success: bool | None = None) -> None:
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE builds SET status=?, log=?, success=?,"
            " updated_at=datetime('now') WHERE id=?",
            (status, log[-10000:], success, build_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_builds(repo_id: str) -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM builds WHERE repo_id = ? ORDER BY created_at DESC",
            (repo_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_full_repo(repo_id: str) -> dict:
    """Get a repo with its latest detection, dockerfile, and builds."""
    repo = get_repo(repo_id)
    if not repo:
        return {"error": "Not found"}
    detection = get_detection(repo_id)
    dockerfile = get_dockerfile(repo_id)
    builds = get_builds(repo_id)
    return {
        "repo": repo,
        "detection": detection,
        "dockerfile": dockerfile["content"] if dockerfile else None,
        "builds": builds,
    }


# ── GitHub token operations ──

def save_github_token(token: str, login: str = "") -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM github_tokens")
        conn.execute(
            "INSERT INTO github_tokens (token, github_login) VALUES (?, ?)",
            (token, login),
        )
        conn.commit()
    finally:
        conn.close()


def get_github_token() -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM github_tokens ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_github_token() -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM github_tokens")
        conn.commit()
    finally:
        conn.close()


# ── GitHub Account operations ──

def create_github_account(account_name: str, installation_id: str, access_token: str, token_expires_at: float = 0) -> dict:
    conn = _get_db()
    try:
        aid = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO github_accounts (id, account_name, installation_id, access_token, token_expires_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (aid, account_name, installation_id, access_token, token_expires_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM github_accounts WHERE id = ?", (aid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()

def get_all_github_accounts() -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute("SELECT * FROM github_accounts ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()

def get_github_account(aid: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM github_accounts WHERE id = ?", (aid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()

def delete_github_account(aid: str) -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM github_accounts WHERE id = ?", (aid,))
        conn.commit()
    finally:
        conn.close()

def update_github_account_token(aid: str, access_token: str, expires_at: float) -> None:
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE github_accounts SET access_token=?, token_expires_at=? WHERE id=?",
            (access_token, expires_at, aid),
        )
        conn.commit()
    finally:
        conn.close()


# ── Project operations ──

def create_project(name: str, description: str = "", repo_id: str | None = None,
                   gitignore: str = "") -> dict:
    conn = _get_db()
    try:
        pid = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO projects (id, name, description, repo_id, gitignore)"
            " VALUES (?, ?, ?, ?, ?)",
            (pid, name, description, repo_id, gitignore),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_project(pid: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_projects() -> list[dict]:
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT p.*, r.clone_status as repo_status, r.name as repo_name "
            "FROM projects p LEFT JOIN repos r ON p.repo_id = r.id "
            "ORDER BY p.updated_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def delete_project(pid: str) -> None:
    conn = _get_db()
    try:
        conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()


def update_project(pid: str, **kwargs) -> dict | None:
    conn = _get_db()
    try:
        sets = []
        vals = []
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        if not sets:
            return get_project(pid)
        vals.append(pid)
        sets.append("updated_at = datetime('now')")
        conn.execute(
            f"UPDATE projects SET {', '.join(sets)} WHERE id = ?",
            vals,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()
