import os, sqlite3

TURSO_URL   = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

def get_conn():
    if TURSO_URL and TURSO_TOKEN:
        import libsql_client
        # usa Turso em produção
        return libsql_client.create_client_sync(
            url=TURSO_URL,
            auth_token=TURSO_TOKEN,
        )
    # usa SQLite local em desenvolvimento
    conn = sqlite3.connect("/tmp/crossposter.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if TURSO_URL and TURSO_TOKEN:
        import libsql_client
        client = libsql_client.create_client_sync(
            url=TURSO_URL,
            auth_token=TURSO_TOKEN,
        )
        client.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                open_id TEXT UNIQUE,
                access_token TEXT,
                refresh_token TEXT,
                expires_at TEXT
            )
        """)
        client.execute("""
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
        client.close()
    else:
        conn = sqlite3.connect("/tmp/crossposter.db")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, open_id TEXT UNIQUE,
            access_token TEXT, refresh_token TEXT, expires_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS video_posts (
            id TEXT PRIMARY KEY, user_id TEXT, source_url TEXT,
            caption TEXT, status TEXT DEFAULT 'PENDING',
            publish_id TEXT, error_msg TEXT, created_at TEXT)""")
        conn.commit()
        conn.close()