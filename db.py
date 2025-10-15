# db.py
import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Dict, Any
import pandas as pd
from passlib.hash import argon2, bcrypt, bcrypt_sha256

DB_PATH = Path("healthhub.db")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_conn()
    # 使用者表
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    # 血壓表（含 user_id 外鍵）
    conn.execute("""
    CREATE TABLE IF NOT EXISTS blood_pressure (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        datetime TEXT NOT NULL,
        systolic REAL NOT NULL,
        diastolic REAL NOT NULL,
        pulse REAL NOT NULL,
        meds TEXT DEFAULT '',
        note TEXT DEFAULT '',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    # 舊表升級容錯（若缺欄位就補）
    try:
        conn.execute("ALTER TABLE blood_pressure ADD COLUMN user_id INTEGER;")
        conn.execute("UPDATE blood_pressure SET user_id = 1 WHERE user_id IS NULL;")
    except Exception:
        pass
    conn.commit()
    conn.close()

# ---------- 密碼雜湊：新帳號一律 Argon2；相容舊 bcrypt / bcrypt_sha256 ----------
def _hash_password(password: str) -> str:
    # Argon2 沒有 72 bytes 限制
    return argon2.hash(password)

def _identify_scheme(ph: str) -> str:
    # 回傳 'argon2' / 'bcrypt_sha256' / 'bcrypt' / 'unknown'
    try:
        if argon2.identify(ph):
            return "argon2"
    except Exception:
        pass
    try:
        if bcrypt_sha256.identify(ph):
            return "bcrypt_sha256"
    except Exception:
        pass
    try:
        if bcrypt.identify(ph):
            return "bcrypt"
    except Exception:
        pass
    return "unknown"

def _verify_password(password: str, password_hash: str) -> bool:
    scheme = _identify_scheme(password_hash)
    try:
        if scheme == "argon2":
            return argon2.verify(password, password_hash)
        if scheme == "bcrypt_sha256":
            return bcrypt_sha256.verify(password, password_hash)
        if scheme == "bcrypt":
            return bcrypt.verify(password, password_hash)
    except Exception:
        return False
    return False

def maybe_upgrade_password(user_id: int, password: str, password_hash: str):
    """登入成功後，若是舊雜湊（bcrypt*/…），就升級成 argon2。"""
    if _identify_scheme(password_hash) != "argon2":
        try:
            new_hash = _hash_password(password)
            conn = get_conn()
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
            conn.commit()
            conn.close()
        except Exception:
            # 升級失敗不阻斷登入流程
            pass

# ---------- 使用者 ----------
def create_user(email: str, name: str, password: str) -> int:
    email = (email or "").strip().lower()
    name = (name or "").strip() or email.split("@")[0]
    if len(password) < 6:
        raise ValueError("Password too short")
    ph = _hash_password(password)  # Argon2
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
        (email, name, ph)
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, password_hash FROM users WHERE email = ?",
        ((email or "").strip().lower(),)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "name": row[2], "password_hash": row[3]}

def verify_password(password: str, password_hash: str) -> bool:
    return _verify_password(password, password_hash)

# ---------- 血壓 ----------
def add_bp(user_id: int, rec: Dict[str, Any]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO blood_pressure (user_id, datetime, systolic, diastolic, pulse, meds, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, rec["datetime"], rec["systolic"], rec["diastolic"], rec["pulse"],
          rec.get("meds",""), rec.get("note","")))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def update_bp(user_id: int, rec_id: int, fields: Dict[str, Any]):
    keys, vals = [], []
    for k, v in fields.items():
        keys.append(f"{k} = ?"); vals.append(v)
    vals.extend([user_id, rec_id])
    sql = f"UPDATE blood_pressure SET {', '.join(keys)} WHERE user_id = ? AND id = ?"
    conn = get_conn()
    conn.execute(sql, tuple(vals))
    conn.commit()
    conn.close()

def delete_bp(user_id: int, ids: Iterable[int]):
    ids = list(ids)
    if not ids: return
    q = ",".join("?" for _ in ids)
    conn = get_conn()
    conn.execute(f"DELETE FROM blood_pressure WHERE user_id = ? AND id IN ({q})", (user_id, *ids))
    conn.commit()
    conn.close()

def list_bp(user_id: int, start_iso: Optional[str]=None, end_iso: Optional[str]=None) -> pd.DataFrame:
    conn = get_conn()
    if start_iso and end_iso:
        df = pd.read_sql_query("""
            SELECT id, datetime, systolic, diastolic, pulse, meds, note
            FROM blood_pressure
            WHERE user_id = ? AND datetime BETWEEN ? AND ?
            ORDER BY datetime
        """, conn, params=(user_id, start_iso, end_iso))
    else:
        df = pd.read_sql_query("""
            SELECT id, datetime, systolic, diastolic, pulse, meds, note
            FROM blood_pressure
            WHERE user_id = ?
            ORDER BY datetime
        """, conn, params=(user_id,))
    conn.close()
    return df
