import httpx

TURSO_URL   = "libsql://crossposter-joaogomes2120.aws-us-west-2.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NzgxODc5ODQsImlkIjoiMDE5ZTA0NDEtZWEwMS03NWI1LWIzNDQtZjRhZWFjYWY2ZWY3IiwicmlkIjoiOWNmY2UzZTctOWZmNi00OWYyLTk1MDEtOTIyMjFjMzVmMDkzIn0.5bJpHG61VivN7kC1FkSZPHpqWar0NOOK7w-mt2kl2TAmJrjzAcNfjJyhM5Whm0u4jFNln78a9sK_SSEv0GPbAQ"
TURSO_HTTP  = "https://crossposter-joaogomes2120.aws-us-west-2.turso.io"

def turso_execute(sql, args=[]):
    resp = httpx.post(
        f"{TURSO_HTTP}/v2/pipeline",
        headers={
            "Authorization": f"Bearer {TURSO_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": [{"type": "text", "value": str(a)} for a in args]}},
            {"type": "close"}
        ]},
        timeout=10,
    )
    return resp.json()

def turso_query(sql, args=[]):
    result = turso_execute(sql, args)
    try:
        rs = result["results"][0]["response"]["result"]
        cols = [c["name"] for c in rs["cols"]]
        return [dict(zip(cols, [v.get("value") for v in row])) for row in rs["rows"]]
    except:
        return []

def init_db():
    turso_execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, open_id TEXT UNIQUE,
        access_token TEXT, refresh_token TEXT, expires_at TEXT)""")
    
    turso_execute("""CREATE TABLE IF NOT EXISTS video_posts (
        id TEXT PRIMARY KEY, user_id TEXT, source_url TEXT,
        caption TEXT, status TEXT DEFAULT 'PENDING',
        publish_id TEXT, error_msg TEXT, created_at TEXT)""")
    
    turso_execute("""CREATE TABLE IF NOT EXISTS schedule_configs (
        user_id TEXT PRIMARY KEY,
        posts_per_day INTEGER DEFAULT 1,
        start_hour INTEGER DEFAULT 8,
        end_hour INTEGER DEFAULT 22,
        auto_delete BOOLEAN DEFAULT 1)""")

    # Attempt to add published_at column to video_posts in case it doesn't exist
    turso_execute("ALTER TABLE video_posts ADD COLUMN published_at TEXT;")