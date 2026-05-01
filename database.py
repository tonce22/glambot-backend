import sqlite3
import json
import bcrypt
from datetime import datetime
from typing import Optional
from models import InvoiceCreate, InvoiceUpdate

DB_PATH = "glambot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','manager','viewer')),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                total REAL NOT NULL DEFAULT 0,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS counter (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                value INTEGER NOT NULL DEFAULT 0
            );

            INSERT OR IGNORE INTO counter (id, value) VALUES (1, 0);

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                date TEXT,
                notes TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


def seed_default_admin():
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not exists:
            pw_hash = bcrypt.hashpw(b"glambot2024", bcrypt.gensalt()).decode()
            conn.execute(
                "INSERT INTO users (name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                ("Tezo Tabidze", "admin", pw_hash, "admin")
            )


def next_invoice_number() -> str:
    with get_conn() as conn:
        conn.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
        row = conn.execute("SELECT value FROM counter WHERE id = 1").fetchone()
        year = datetime.now().year
        return f"GBG-{year}-{row['value']:04d}"


# ── USERS ─────────────────────────────────────────────────

def _user_dict(row) -> dict:
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "username": row["username"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "created_at": row["created_at"]
    }


def get_all_users() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_dict(row)


def get_user_by_username(username: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _user_dict(row)


def create_user(name: str, username: str, password_hash: str, role: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, username, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, username, password_hash, role)
        )
        return cur.lastrowid


def update_user(user_id: int, name: str, username: str, password_hash: Optional[str], role: str):
    with get_conn() as conn:
        if password_hash:
            conn.execute(
                "UPDATE users SET name=?, username=?, password_hash=?, role=? WHERE id=?",
                (name, username, password_hash, role, user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET name=?, username=?, role=? WHERE id=?",
                (name, username, role, user_id)
            )


def delete_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ── INVOICES ──────────────────────────────────────────────

def _invoice_dict(row) -> Optional[dict]:
    if not row:
        return None
    d = dict(row)
    d["items"] = json.loads(d.get("items") or "[]")
    return d


def get_all_invoices() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM invoices ORDER BY id DESC"
        ).fetchall()
        return [_invoice_dict(r) for r in rows]


def get_invoice_by_id(invoice_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return _invoice_dict(row)


def create_invoice(data: InvoiceCreate, user_id: int) -> int:
    number = next_invoice_number()
    total = sum(item.qty * item.price for item in data.items)
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO invoices
            (number, language, status, issue_date, due_date, event_type, event_date,
             client_name, client_phone, client_email, client_address,
             bank_name, bank_account, notes, items, total, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            number, data.language, data.status,
            data.issue_date, data.due_date, data.event_type, data.event_date,
            data.client_name, data.client_phone, data.client_email, data.client_address,
            data.bank_name, data.bank_account, data.notes,
            json.dumps([i.dict() for i in data.items]),
            total, user_id
        ))
        return cur.lastrowid


def update_invoice(invoice_id: int, data: InvoiceUpdate):
    total = sum(item.qty * item.price for item in data.items)
    with get_conn() as conn:
        conn.execute("""
            UPDATE invoices SET
            language=?, status=?, issue_date=?, due_date=?, event_type=?, event_date=?,
            client_name=?, client_phone=?, client_email=?, client_address=?,
            bank_name=?, bank_account=?, notes=?, items=?, total=?,
            updated_at=datetime('now')
            WHERE id=?
        """, (
            data.language, data.status,
            data.issue_date, data.due_date, data.event_type, data.event_date,
            data.client_name, data.client_phone, data.client_email, data.client_address,
            data.bank_name, data.bank_account, data.notes,
            json.dumps([i.dict() for i in data.items]),
            total, invoice_id
        ))


def delete_invoice(invoice_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))


# ── EXPENSES ──────────────────────────────────────────────

def get_all_expenses() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]

def get_expense_by_id(expense_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        return dict(row) if row else None

def create_expense(title: str, amount: float, category: str, date: str, notes: str, user_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO expenses (title, amount, category, date, notes, created_by) VALUES (?,?,?,?,?,?)",
            (title, amount, category, date, notes, user_id)
        )
        return cur.lastrowid

def update_expense(expense_id: int, title: str, amount: float, category: str, date: str, notes: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=?, date=?, notes=? WHERE id=?",
            (title, amount, category, date, notes, expense_id)
        )

def delete_expense(expense_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

def get_expense_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COALESCE(SUM(amount),0) as s FROM expenses").fetchone()["s"]
        by_cat = conn.execute(
            "SELECT category, COALESCE(SUM(amount),0) as s FROM expenses GROUP BY category"
        ).fetchall()
        return {"total_spent": total, "by_category": {r["category"]: r["s"] for r in by_cat}}


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM invoices").fetchone()["c"]
        paid = conn.execute("SELECT COUNT(*) as c FROM invoices WHERE status='paid'").fetchone()["c"]
        pending = conn.execute("SELECT COUNT(*) as c FROM invoices WHERE status='pending'").fetchone()["c"]
        draft = conn.execute("SELECT COUNT(*) as c FROM invoices WHERE status='draft'").fetchone()["c"]
        revenue = conn.execute("SELECT COALESCE(SUM(total),0) as s FROM invoices WHERE status='paid'").fetchone()["s"]
        return {"total": total, "paid": paid, "pending": pending, "draft": draft, "revenue": revenue}
