from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/")
def root():
    return {"status": "online", "app": "CrossPoster"}

@app.get("/health")
def health():
    return {"healthy": True}

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

@app.get("/auth/callback")
def auth_callback():
    return {"status": "callback ok"}

@app.get("/tiktok9ASD673ZVjlamdnZqO7DIPfyWdfXZGE0.txt")
def tiktok_verify():
    return HTMLResponse("tiktok9ASD673ZVjlamdnZqO7DIPfyWdfXZGE0")