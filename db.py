import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.db")


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, stock_code)
        )
    """)
    conn.commit()
    conn.close()


def add_stock(username, code, name):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO watchlist (username, stock_code, stock_name) VALUES (?, ?, ?)",
            (username, code, name)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_stock(username, code):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        "DELETE FROM watchlist WHERE username = ? AND stock_code = ?",
        (username, code)
    )
    conn.commit()
    conn.close()


def get_watchlist(username):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        "SELECT stock_code, stock_name FROM watchlist WHERE username = ? ORDER BY added_at DESC",
        (username,)
    )
    rows = c.fetchall()
    conn.close()
    return rows