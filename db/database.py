import sqlite3, os

DB_PATH = "/tmp/crossposter.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            open_id TEXT UNIQUE,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS video_posts (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            source_url TEXT,
            caption TEXT,
            status TEXT DEFAULT 'PENDING',
            publish_id TEXT,
            error_msg TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()