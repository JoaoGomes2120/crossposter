"""
save_cookies.py — Rode esse script NA SUA MAQUINA LOCAL.

Ele abre o Chrome, voce faz login no TikTok normalmente,
e os cookies sao salvos no banco Turso automaticamente.

Uso:
  pip install playwright
  playwright install chromium
  python save_cookies.py SEU_USER_ID

Onde SEU_USER_ID e o ID que aparece na URL da sua dashboard:
  /dashboard?user_id=XXXXX
"""

import sys, json
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from db.database import turso_execute, turso_query, init_db

def main():
    if len(sys.argv) < 2:
        print("Uso: python save_cookies.py SEU_USER_ID")
        print("Exemplo: python save_cookies.py 263195c2-8292-45c3-890b-f93a6f633267")
        sys.exit(1)

    user_id = sys.argv[1]
    init_db()

    print("=" * 50)
    print("CROSSPOSTER — Login no TikTok")
    print("=" * 50)
    print()
    print("Um navegador vai abrir agora.")
    print("Faca login na sua conta do TikTok normalmente.")
    print("Quando terminar o login e ver a pagina inicial,")
    print("VOLTE AQUI e aperte ENTER.")
    print()

    with sync_playwright() as p:
        import tempfile, os
        user_dir = os.path.join(tempfile.gettempdir(), 'tiktok_login_dir')
        
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_dir,
            headless=False,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.tiktok.com/login")

        while True:
            resp = input("\n>>> FEZ LOGIN? Digite 'OK' e aperte ENTER para salvar os cookies: ")
            if resp.strip().lower() == 'ok':
                break

        cookies = context.cookies()
        context.close()

    if not cookies:
        print("ERRO: Nenhum cookie capturado. Tente novamente.")
        sys.exit(1)

    cookies_json = json.dumps(cookies)
    now = datetime.now(timezone.utc).isoformat()

    existing = turso_query("SELECT user_id FROM browser_cookies WHERE user_id=?", [user_id])
    if existing:
        turso_execute("UPDATE browser_cookies SET cookies_json=?, updated_at=? WHERE user_id=?",
                      [cookies_json, now, user_id])
    else:
        turso_execute("INSERT INTO browser_cookies (user_id, cookies_json, updated_at) VALUES (?,?,?)",
                      [user_id, cookies_json, now])

    print()
    print(f"Cookies salvos com sucesso! ({len(cookies)} cookies capturados)")
    print(f"User ID: {user_id}")
    print("Agora o worker pode postar videos automaticamente.")

if __name__ == "__main__":
    main()
