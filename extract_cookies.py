import sys, json
from datetime import datetime, timezone

try:
    import browser_cookie3
except ImportError:
    print("Instalando pacote necessario...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "browser-cookie3"])
    import browser_cookie3

from db.database import turso_execute, turso_query, init_db

def main():
    if len(sys.argv) < 2:
        print("Uso: python extract_cookies.py SEU_USER_ID")
        sys.exit(1)

    user_id = sys.argv[1]
    init_db()

    print("=" * 50)
    print("CROSSPOSTER — Extrator de Cookies (Sem Login)")
    print("=" * 50)
    print("Lendo cookies dos seus navegadores normais (Chrome, Edge, Brave)...")

    cj = None
    browsers = [
        ("Chrome", browser_cookie3.chrome),
        ("Edge", browser_cookie3.edge),
        ("Brave", browser_cookie3.brave),
        ("Firefox", browser_cookie3.firefox)
    ]

    for name, func in browsers:
        try:
            print(f"Tentando ler do {name}...")
            cj_temp = func(domain_name='.tiktok.com')
            if len(list(cj_temp)) > 0:
                print(f"  Encontrou cookies no {name}!")
                cj = cj_temp
                break
        except Exception as e:
            # Silently ignore errors for individual browsers
            pass

    if not cj:
        print("Erro: Nao foi possivel extrair de nenhum navegador.")
        print("1. Certifique-se de que fechou TODAS as janelas do seu navegador (Chrome/Edge/Brave).")
        print("2. Certifique-se de que voce esta logado no site do TikTok neste PC.")
        sys.exit(1)

    playwright_cookies = []
    for cookie in cj:
        playwright_cookies.append({
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.secure,
            "httpOnly": bool(cookie.has_nonstandard_attr('HttpOnly')),
            "sameSite": "Lax"
        })

    if not playwright_cookies:
        print()
        print("ERRO: Nenhum cookie do TikTok encontrado.")
        print("Por favor, abra o seu navegador normal (Google Chrome ou Edge ou Brave).")
        print("Faca login no TikTok (tiktok.com) normalmente.")
        print("Depois feche o navegador e rode este script novamente.")
        sys.exit(1)

    cookies_json = json.dumps(playwright_cookies)
    now = datetime.now(timezone.utc).isoformat()

    existing = turso_query("SELECT user_id FROM browser_cookies WHERE user_id=?", [user_id])
    if existing:
        turso_execute("UPDATE browser_cookies SET cookies_json=?, updated_at=? WHERE user_id=?",
                      [cookies_json, now, user_id])
    else:
        turso_execute("INSERT INTO browser_cookies (user_id, cookies_json, updated_at) VALUES (?,?,?)",
                      [user_id, cookies_json, now])

    print()
    print(f"✅ SUCESSO! {len(playwright_cookies)} cookies foram copiados diretamente do seu navegador.")
    print(f"Você nao precisa logar pela tela preta do Playwright!")
    print("A badge verde de 'Browser Conectado' já deve aparecer no seu Dashboard.")

if __name__ == "__main__":
    main()
