import os
import secrets
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

CLIENT_ID     = os.getenv("TIKTOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("TIKTOK_REDIRECT_URI")

@app.get("/")
def root():
    return {"status": "online", "app": "CrossPoster"}

@app.get("/health")
def health():
    return {"healthy": True}

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
async def auth_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return {"error": error}
    if not code:
        return {"error": "codigo nao recebido"}

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
    if "access_token" in data:
        return {
            "status":        "autenticado",
            "open_id":       data.get("open_id"),
            "access_token":  data.get("access_token"),
            "expires_in":    data.get("expires_in"),
        }
    return {"error": data}

@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return """
    <html><head><title>Política de Privacidade - CrossPoster</title></head>
    <body style="font-family:Arial;max-width:800px;margin:40px auto;padding:20px">
    <h1>Política de Privacidade</h1>
    <p>Última atualização: 06/05/2026</p>
    <h2>1. Informações coletadas</h2>
    <p>Coletamos endereço de e-mail e dados de autenticação via TikTok OAuth 2.0.</p>
    <h2>2. Uso das informações</h2>
    <p>As informações são usadas exclusivamente para autenticar o usuário e realizar uploads de vídeos no TikTok em nome do criador.</p>
    <h2>3. Segurança</h2>
    <p>Todos os tokens de acesso são armazenados com criptografia AES-256.</p>
    <h2>4. Compartilhamento</h2>
    <p>Não vendemos nem compartilhamos dados. As informações são enviadas apenas à API oficial do TikTok.</p>
    <h2>5. Contato</h2>
    <p>joaogumes23w@outlook.com</p>
    </body></html>
    """

@app.get("/terms", response_class=HTMLResponse)
def terms():
    return """
    <html><head><title>Termos de Uso - CrossPoster</title></head>
    <body style="font-family:Arial;max-width:800px;margin:40px auto;padding:20px">
    <h1>Termos de Uso</h1>
    <p>Última atualização: 06/05/2026</p>
    <h2>1. Aceitação</h2>
    <p>Ao usar o CrossPoster, você concorda com estes termos.</p>
    <h2>2. Uso permitido</h2>
    <p>O CrossPoster é uma ferramenta para criadores publicarem seus próprios vídeos no TikTok. É proibido usar para publicar conteúdo de terceiros sem autorização.</p>
    <h2>3. Responsabilidade</h2>
    <p>O usuário é responsável pelo conteúdo que publica. O CrossPoster não se responsabiliza por violações das diretrizes do TikTok.</p>
    <h2>4. Conta TikTok</h2>
    <p>O uso indevido que resulte em banimento de conta TikTok é de responsabilidade exclusiva do usuário.</p>
    <h2>5. Contato</h2>
    <p>joaogumes23w@outlook.com</p>
    </body></html>
    """

@app.get("/tiktok9emzl9xlyeT0KDdRDvSi5aULRsjNFXha.txt")
def tiktok_verify():
    return HTMLResponse("tiktok-developers-site-verification=9emzl9xIyeT0KDdRDvSi5aULRsjNFXha")