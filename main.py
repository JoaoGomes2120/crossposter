import os, secrets, uuid, json, sys
import httpx
import threading, subprocess
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from db.database import init_db, turso_execute, turso_query
from datetime import datetime, timezone, timedelta

app = FastAPI()

CLIENT_ID     = os.getenv("TIKTOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("TIKTOK_REDIRECT_URI")

@app.on_event("startup")
def startup():
    init_db()
    def run_worker():
        subprocess.run([sys.executable, "-u", "worker.py"])
    threading.Thread(target=run_worker, daemon=True).start()

@app.get("/login")
def login():
    state = secrets.token_urlsafe(16)
    url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=user.info.basic,video.upload,video.publish"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&prompt=consent"
    )
    return RedirectResponse(url)

@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    if error or not code:
        return {"error": error or "codigo nao recebido"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key":    CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code":          code,
                "grant_type":    "authorization_code",
                "redirect_uri":  REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    data = resp.json()
    if "access_token" not in data:
        return {"error": data}

    open_id    = data["open_id"]
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])).isoformat()

    existing = turso_query("SELECT id FROM users WHERE open_id=?", [open_id])
    if existing:
        user_id = existing[0]["id"]
        turso_execute("UPDATE users SET access_token=?, refresh_token=?, expires_at=? WHERE open_id=?",
            [data["access_token"], data.get("refresh_token",""), expires_at, open_id])
    else:
        user_id = str(uuid.uuid4())
        turso_execute("INSERT INTO users VALUES (?,?,?,?,?)",
            [user_id, open_id, data["access_token"], data.get("refresh_token",""), expires_at])

    return RedirectResponse(f"/dashboard?user_id={user_id}")

@app.get("/config")
def get_config(user_id: str):
    cfg = turso_query("SELECT * FROM schedule_configs WHERE user_id=?", [user_id])
    if cfg: return cfg[0]
    return {"posts_per_day": 1, "start_hour": 8, "end_hour": 22, "auto_delete": 1}

@app.post("/config")
async def save_config(user_id: str, posts: int):
    # Only exposing posts_per_day for simplicity in the UI to match user requests
    existing = turso_query("SELECT user_id FROM schedule_configs WHERE user_id=?", [user_id])
    if existing:
        turso_execute("UPDATE schedule_configs SET posts_per_day=? WHERE user_id=?",
                      [posts, user_id])
    else:
        turso_execute("INSERT INTO schedule_configs (user_id, posts_per_day) VALUES (?, ?)",
                      [user_id, posts])
    return {"status": "ok"}

@app.post("/add-video")
async def add_video(user_id: str, source_url: str, caption: str):
    user = turso_query("SELECT * FROM users WHERE id=?", [user_id])
    if not user:
        return {"error": "usuario nao encontrado"}

    post_id = str(uuid.uuid4())
    turso_execute("INSERT INTO video_posts (id, user_id, source_url, caption, status, created_at) VALUES (?,?,?,?,?,?)",
        [post_id, user_id, source_url, caption, "PENDING", datetime.now(timezone.utc).isoformat()])

    return {"status": "adicionado", "post_id": post_id}

@app.post("/post-now")
def post_now(post_id: str):
    turso_execute("UPDATE video_posts SET status='FORCE_POST' WHERE id=?", [post_id])
    return {"status": "ok"}

@app.get("/videos")
def get_videos(user_id: str):
    return turso_query(
        "SELECT * FROM video_posts WHERE user_id=? ORDER BY created_at DESC", [user_id]
    )

@app.get("/debug-users")
def debug_users():
    return turso_query("SELECT id, open_id, expires_at FROM users")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(user_id: str = ""):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CrossPoster</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; background: #0f0f0f; color: #fff; padding: 24px; }}
  h1 {{ font-size: 22px; margin-bottom: 20px; }}
  .card {{ background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
  input, textarea {{ width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #333; background: #111; color: #fff; font-size: 14px; margin-top: 6px; }}
  textarea {{ height: 80px; resize: none; }}
  label {{ font-size: 12px; color: #aaa; }}
  button {{ background: #fe2c55; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-size: 14px; cursor: pointer; margin-top: 12px; width: 100%; }}
  button:hover {{ opacity: 0.85; }}
  .video-item {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #222; }}
  .badge {{ font-size: 11px; padding: 4px 10px; border-radius: 20px; font-weight: bold; }}
  .PENDING {{ background: #333; color: #aaa; }}
  .FORCE_POST {{ background: #9a6a00; color: #fde047; }}
  .DOWNLOADING {{ background: #1e3a8a; color: #bfdbfe; }}
  .UPLOADING {{ background: #3b0764; color: #e9d5ff; }}
  .PUBLISHED {{ background: #1a3a2a; color: #4ade80; }}
  .FAILED {{ background: #3a1a1a; color: #f87171; }}
  .url {{ font-size: 11px; color: #666; margin-top: 2px; }}
</style>
</head>
<body>
<div class="card" style="display:flex; justify-content:space-between; align-items:center;">
  <div>
    <h2 style="font-size:15px;margin-bottom:4px">Definições de Postagem Automática</h2>
    <p style="font-size:12px;color:#aaa">O sistema publicará automaticamente na janela de 08:00 às 22:00.</p>
  </div>
  <div style="display:flex; gap:8px; align-items:center;">
    <label>Vídeos por dia:</label>
    <input type="number" id="posts-per-day" min="1" max="10" value="1" style="width:60px; margin:0;" />
    <button onclick="saveConfig()" style="width:auto; margin:0;">Salvar</button>
  </div>
</div>
<div class="card">
  <label>URL do vídeo (Sua conta)</label>
  <input type="text" id="url" placeholder="https://www.kwai.com/@voce/video/..."/>
  <label style="margin-top:12px;display:block">Legenda + hashtags</label>
  <textarea id="caption" placeholder="Legenda para o TikTok..."></textarea>
  <button onclick="addVideo()">+ Fila de Automação</button>
</div>
<div class="card">
  <h2 style="font-size:15px;margin-bottom:12px">Fila e Publicados</h2>
  <div id="video-list"><p style="color:#666;font-size:13px">Carregando...</p></div>
</div>
<script>
const USER_ID = "{user_id}";

async function loadConfig() {{
  const r = await fetch(`/config?user_id=${{USER_ID}}`);
  if (r.ok) {{
      const cfg = await r.json();
      document.getElementById('posts-per-day').value = cfg.posts_per_day || 1;
  }}
}}

async function saveConfig() {{
  const posts = document.getElementById('posts-per-day').value;
  await fetch(`/config?user_id=${{USER_ID}}&posts=${{posts}}`, {{method:'POST'}});
  alert('Salvo com sucesso! Agora processaremos essa quantidade por dia.');
}}

async function loadVideos() {{
  const r = await fetch(`/videos?user_id=${{USER_ID}}`);
  const videos = await r.json();
  const list = document.getElementById('video-list');
  if (!videos.length) {{ list.innerHTML = '<p style="color:#666;font-size:13px">Nenhum vídeo ainda.</p>'; return; }}
  list.innerHTML = videos.map(v => `
    <div class="video-item">
      <div>
        <div style="font-size:13px;font-weight:500">${{v.caption}}</div>
        <div class="url">${{v.source_url}}</div>
      </div>
      <div>
        ${{ v.status === 'PENDING' ? `<button onclick="postNow('${{v.id}}')" style="width:auto;margin:0 10px;padding:4px 8px;font-size:11px;background:#444;">Postar Agora</button>` : '' }}
        <span class="badge ${{v.status}}">${{v.status}}</span>
      </div>
    </div>
  `).join('');
}}

async function postNow(postId) {{
  await fetch(`/post-now?post_id=${{postId}}`, {{method:'POST'}});
  alert('Vídeo movido para prioridade! Aguarde a mudança do status de FORCE_POST para PUBLISHED nos próximos segundos.');
  loadVideos();
}}

async function addVideo() {{
  const url = document.getElementById('url').value.trim();
  const caption = document.getElementById('caption').value.trim();
  if (!url || !caption) {{ alert('Preencha todos os campos'); return; }}
  await fetch(`/add-video?user_id=${{USER_ID}}&source_url=${{encodeURIComponent(url)}}&caption=${{encodeURIComponent(caption)}}`, {{method:'POST'}});
  document.getElementById('url').value = '';
  document.getElementById('caption').value = '';
  loadVideos();
}}
loadConfig();
loadVideos();
setInterval(loadVideos, 5000);
</script>
</body>
</html>"""

@app.get("/")
def root():
    return RedirectResponse("/login")

@app.get("/health")
def health():
    return {"healthy": True}

@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return """<html><body style="font-family:Arial;max-width:800px;margin:40px auto;padding:20px">
    <h1>Política de Privacidade</h1><p>Última atualização: 06/05/2026</p>
    <h2>1. Informações coletadas</h2><p>Coletamos e-mail e dados de autenticação via TikTok OAuth 2.0.</p>
    <h2>2. Uso</h2><p>Exclusivamente para autenticar e realizar uploads no TikTok.</p>
    <h2>3. Segurança</h2><p>Tokens armazenados com criptografia AES-256.</p>
    <h2>4. Contato</h2><p>joaogumes23w@outlook.com</p></body></html>"""

@app.get("/terms", response_class=HTMLResponse)
def terms():
    return """<html><body style="font-family:Arial;max-width:800px;margin:40px auto;padding:20px">
    <h1>Termos de Uso</h1><p>Última atualização: 06/05/2026</p>
    <h2>1. Uso permitido</h2><p>Apenas para publicar seus próprios vídeos no TikTok.</p>
    <h2>2. Responsabilidade</h2><p>O usuário é responsável pelo conteúdo publicado.</p>
    <h2>3. Contato</h2><p>joaogumes23w@outlook.com</p></body></html>"""

@app.get("/tiktok9emzl9xlyeT0KDdRDvSi5aULRsjNFXha.txt")
def tiktok_verify():
    return HTMLResponse("tiktok-developers-site-verification=9emzl9xIyeT0KDdRDvSi5aULRsjNFXha")