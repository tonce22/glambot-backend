import pymysql
import pymysql.cursors
import json
import bcrypt
import os
from datetime import datetime
from typing import Optional
from models import InvoiceCreate, InvoiceUpdate

# ── MySQL connection settings (set these as env vars in cPanel Python App) ──
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_DB   = os.getenv("MYSQL_DB",   "glambotgec0a_glambot")
MYSQL_USER = os.getenv("MYSQL_USER", "glambotgec0a_user")
MYSQL_PASS = os.getenv("MYSQL_PASS", "")


def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255),
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('admin','manager','viewer') NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT NOW()
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    number VARCHAR(64) NOT NULL UNIQUE,
                    language VARCHAR(8) NOT NULL DEFAULT 'en',
                    status ENUM('draft','pending','paid') NOT NULL DEFAULT 'draft',
                    issue_date VARCHAR(32),
                    due_date VARCHAR(32),
                    event_type VARCHAR(255),
                    event_date VARCHAR(32),
                    client_name VARCHAR(255),
                    client_phone VARCHAR(64),
                    client_email VARCHAR(255),
                    client_address TEXT,
                    bank_name VARCHAR(255),
                    bank_account VARCHAR(255),
                    notes TEXT,
                    items LONGTEXT NOT NULL DEFAULT '[]',
                    total DOUBLE NOT NULL DEFAULT 0,
                    created_by INT,
                    created_at DATETIME NOT NULL DEFAULT NOW(),
                    updated_at DATETIME NOT NULL DEFAULT NOW()
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS counter (
                    id INT PRIMARY KEY DEFAULT 1,
                    value INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB
            """)
            cur.execute("INSERT IGNORE INTO counter (id, value) VALUES (1, 0)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    amount DOUBLE NOT NULL,
                    category VARCHAR(64) NOT NULL DEFAULT 'other',
                    date VARCHAR(32),
                    notes TEXT,
                    file_data LONGTEXT,
                    file_name VARCHAR(255),
                    file_type VARCHAR(64),
                    created_by INT,
                    created_at DATETIME NOT NULL DEFAULT NOW()
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
    finally:
        conn.close()


def seed_default_admin():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = 'admin'")
            if not cur.fetchone():
                pw_hash = bcrypt.hashpw(b"glambot2024", bcrypt.gensalt()).decode()
                cur.execute(
                    "INSERT INTO users (name, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                    ("Rezo Tabidze", "admin", pw_hash, "admin")
                )
    finally:
        conn.close()


def next_invoice_number() -> str:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
            cur.execute("SELECT value FROM counter WHERE id = 1")
            row = cur.fetchone()
            year = datetime.now().year
            return f"GBG-{year}-{row['value']:04d}"
    finally:
        conn.close()


# ── USERS ─────────────────────────────────────────────────

def get_all_users() -> list:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, username, email, role, created_at FROM users ORDER BY id")
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def create_user(name: str, username: str, email: Optional[str], password_hash: str, role: str) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, username, email, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
                (name, username, email, password_hash, role)
            )
            return cur.lastrowid
    finally:
        conn.close()


def update_user(user_id: int, name: str, username: str, email: Optional[str], password_hash: Optional[str], role: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if password_hash:
                cur.execute(
                    "UPDATE users SET name=%s, username=%s, email=%s, password_hash=%s, role=%s WHERE id=%s",
                    (name, username, email, password_hash, role, user_id)
                )
            else:
                cur.execute(
                    "UPDATE users SET name=%s, username=%s, email=%s, role=%s WHERE id=%s",
                    (name, username, email, role, user_id)
                )
    finally:
        conn.close()


def delete_user(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    finally:
        conn.close()


# ── INVOICES ──────────────────────────────────────────────

def _invoice_dict(row) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    d["items"] = json.loads(d.get("items") or "[]")
    return d


def get_all_invoices() -> list:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM invoices ORDER BY id DESC")
            return [_invoice_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_invoice_by_id(invoice_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
            return _invoice_dict(cur.fetchone())
    finally:
        conn.close()


def create_invoice(data: InvoiceCreate, user_id: int) -> int:
    number = next_invoice_number()
    total = sum(item.qty * item.price for item in data.items)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO invoices
                (number, language, status, issue_date, due_date, event_type, event_date,
                 client_name, client_phone, client_email, client_address,
                 bank_name, bank_account, notes, items, total, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                number, data.language, data.status,
                data.issue_date, data.due_date, data.event_type, data.event_date,
                data.client_name, data.client_phone, data.client_email, data.client_address,
                data.bank_name, data.bank_account, data.notes,
                json.dumps([i.dict() for i in data.items]),
                total, user_id
            ))
            return cur.lastrowid
    finally:
        conn.close()


def update_invoice(invoice_id: int, data: InvoiceUpdate):
    total = sum(item.qty * item.price for item in data.items)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE invoices SET
                language=%s, status=%s, issue_date=%s, due_date=%s,
                event_type=%s, event_date=%s,
                client_name=%s, client_phone=%s, client_email=%s, client_address=%s,
                bank_name=%s, bank_account=%s, notes=%s, items=%s, total=%s,
                updated_at=NOW()
                WHERE id=%s
            """, (
                data.language, data.status,
                data.issue_date, data.due_date, data.event_type, data.event_date,
                data.client_name, data.client_phone, data.client_email, data.client_address,
                data.bank_name, data.bank_account, data.notes,
                json.dumps([i.dict() for i in data.items]),
                total, invoice_id
            ))
    finally:
        conn.close()


def delete_invoice(invoice_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))
    finally:
        conn.close()


# ── EXPENSES ──────────────────────────────────────────────

def get_all_expenses() -> list:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC")
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_expense_by_id(expense_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def create_expense(title, amount, category, date, notes, user_id,
                   file_data=None, file_name=None, file_type=None) -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO expenses (title, amount, category, date, notes, file_data, file_name, file_type, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (title, amount, category, date, notes, file_data, file_name, file_type, user_id)
            )
            return cur.lastrowid
    finally:
        conn.close()


def update_expense(expense_id, title, amount, category, date, notes,
                   file_data=None, file_name=None, file_type=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE expenses SET title=%s, amount=%s, category=%s, date=%s, notes=%s, file_data=%s, file_name=%s, file_type=%s WHERE id=%s",
                (title, amount, category, date, notes, file_data, file_name, file_type, expense_id)
            )
    finally:
        conn.close()


def delete_expense(expense_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
    finally:
        conn.close()


def get_expense_stats() -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(amount), 0) as s FROM expenses")
            total = cur.fetchone()["s"]
            cur.execute("SELECT category, COALESCE(SUM(amount), 0) as s FROM expenses GROUP BY category")
            by_cat = cur.fetchall()
            return {"total_spent": float(total), "by_category": {r["category"]: float(r["s"]) for r in by_cat}}
    finally:
        conn.close()


def get_stats() -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM invoices")
            total = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) as c FROM invoices WHERE status='paid'")
            paid = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) as c FROM invoices WHERE status='pending'")
            pending = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) as c FROM invoices WHERE status='draft'")
            draft = cur.fetchone()["c"]
            cur.execute("SELECT COALESCE(SUM(total), 0) as s FROM invoices WHERE status='paid'")
            revenue = cur.fetchone()["s"]
            return {"total": total, "paid": paid, "pending": pending, "draft": draft, "revenue": float(revenue)}
    finally:
        conn.close()
