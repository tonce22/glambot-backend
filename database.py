import psycopg2
import psycopg2.extras
import json
import bcrypt
import os
from datetime import datetime
from typing import Optional
from models import InvoiceCreate, InvoiceUpdate

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','manager','viewer')),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id SERIAL PRIMARY KEY,
                    number TEXT NOT NULL UNIQUE,
                    language TEXT NOT NULL DEFAULT 'en',
                    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','pending','paid')),
                    issue_date TEXT,
                    due_date TEXT,
                    event_type TEXT,
                    event_date TEXT,
                    client_name TEXT,
                    client_phone TEXT,
                    client_email TEXT,
                    client_address TEXT,
                    bank_name TEXT,
                    bank_account TEXT,
                    notes TEXT,
                    items TEXT NOT NULL DEFAULT '[]',
                    total DOUBLE PRECISION NOT NULL DEFAULT 0,
                    created_by INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS counter (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    value INTEGER NOT NULL DEFAULT 0
                )
            """)
            cur.execute("""
                INSERT INTO counter (id, value)
                VALUES (1, 0)
                ON CONFLICT DO NOTHING
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    amount DOUBLE PRECISION NOT NULL,
                    category TEXT NOT NULL DEFAULT 'other',
                    date TEXT,
                    notes TEXT,
                    file_data TEXT,
                    file_name TEXT,
                    file_type TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
    finally:
        conn.close()


def seed_default_admin():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("UPDATE counter SET value = value + 1 WHERE id = 1 RETURNING value")
            row = cur.fetchone()
            year = datetime.now().year
            return f"GBG-{year}-{row['value']:04d}"
    finally:
        conn.close()


# ── USERS ─────────────────────────────────────────────────

def get_all_users() -> list:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, name, username, email, role, created_at FROM users ORDER BY id")
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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
                "INSERT INTO users (name, username, email, password_hash, role) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, username, email, password_hash, role)
            )
            return cur.fetchone()[0]
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
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM invoices ORDER BY id DESC")
            return [_invoice_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_invoice_by_id(invoice_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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
                RETURNING id
            """, (
                number, data.language, data.status,
                data.issue_date, data.due_date, data.event_type, data.event_date,
                data.client_name, data.client_phone, data.client_email, data.client_address,
                data.bank_name, data.bank_account, data.notes,
                json.dumps([i.dict() for i in data.items]),
                total, user_id
            ))
            return cur.fetchone()[0]
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
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC")
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_expense_by_id(expense_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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
                "INSERT INTO expenses (title, amount, category, date, notes, file_data, file_name, file_type, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (title, amount, category, date, notes, file_data, file_name, file_type, user_id)
            )
            return cur.fetchone()[0]
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
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
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
