import os, secrets, uuid, httpx
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from db.database import init_db, get_db
from db.models import User, VideoPost
from datetime import datetime, timezone, timedelta

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

CLIENT_ID    = os.getenv("TIKTOK_CLIENT_ID")
CLIENT_SECRET= os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI")

# ── Auth ──────────────────────────────────────────────────────────────────────

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
    )
    return RedirectResponse(url)

@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None, db: AsyncSession = Depends(get_db)):
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

    # Salva ou atualiza usuário no banco
    result = await db.execute(select(User).where(User.open_id == data["open_id"]))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=str(uuid.uuid4()), open_id=data["open_id"])
        db.add(user)

    user.access_token  = data["access_token"]
    user.refresh_token = data.get("refresh_token", "")
    user.expires_at    = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    await db.commit()

    return RedirectResponse(f"/dashboard?user_id={user.id}")

# ── Videos ───────────────────────────────────────────────────────────────────

@app.post("/add-video")
async def add_video(user_id: str, source_url: str, caption: str, db: AsyncSession = Depends(get_db)):
    post = VideoPost(
        id=str(uuid.uuid4()),
        user_id=user_id,
        source_url=source_url,
        caption=caption,
        status="PENDING",
    )
    db.add(post)
    await db.commit()
    return {"status": "adicionado", "post_id": post.id}

@app.get("/videos")
async def get_videos(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VideoPost).where(VideoPost.user_id == user_id).order_by(VideoPost.created_at.desc())
    )
    posts = result.scalars().all()
    return [{"id": p.id, "caption": p.caption, "source_url": p.source_url, "status": p.status} for p in posts]

# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(user_id: str = "", db: AsyncSession = Depends(get_db)):
    return f"""
<!DOCTYPE html>
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
  button {{ background: #fe2c55; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-size: 14px; cursor: pointer; margin-top: 12px; }}
  button:hover {{ opacity: 0.85; }}
  .video-item {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #222; }}
  .badge {{ font-size: 11px; padding: 4px 10px; border-radius: 20px; font-weight: bold; }}
  .PENDING {{ background: #333; color: #aaa; }}
  .PUBLISHED {{ background: #1a3a2a; color: #4ade80; }}
  .FAILED {{ background: #3a1a1a; color: #f87171; }}
  .url {{ font-size: 11px; color: #666; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; }}
</style>
</head>
<body>
<h1>🎬 CrossPoster</h1>

<div class="card">
  <label>URL do vídeo (sua conta)</label>
  <input type="text" id="url" placeholder="https://www.kwai.com/@voce/video/..."/>
  <label style="margin-top:12px;display:block">Legenda + hashtags</label>
  <textarea id="caption" placeholder="Legenda para o TikTok..."></textarea>
  <button onclick="addVideo()">+ Adicionar à fila</button>
</div>

<div class="card">
  <h2 style="font-size:15px;margin-bottom:12px">Fila de publicação</h2>
  <div id="video-list"><p style="color:#666;font-size:13px">Carregando...</p></div>
</div>

<script>
const USER_ID = "{user_id}";

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
      <span class="badge ${{v.status}}">${{v.status}}</span>
    </div>
  `).join('');
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

loadVideos();
setInterval(loadVideos, 5000);
</script>
</body>
</html>
"""

# ── Static ────────────────────────────────────────────────────────────────────

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