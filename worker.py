import os, time, tempfile, json, math
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

import yt_dlp
from db.database import turso_query, turso_execute

def download_video(url, output_path):
    ydl_opts = {
        "outtmpl": output_path,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def upload_via_browser(video_path, caption, cookies_json):
    """Upload video to TikTok using Playwright browser automation."""
    from playwright.sync_api import sync_playwright

    cookies = json.loads(cookies_json)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Load saved cookies
        context.add_cookies(cookies)

        page = context.new_page()

        # Navigate to TikTok upload page
        print("  Abrindo pagina de upload...")
        page.goto("https://www.tiktok.com/creator#/upload?scene=creator_center", wait_until="networkidle", timeout=60000)
        time.sleep(3)

        # Check if we're logged in (if redirected to login, cookies expired)
        if "/login" in page.url:
            browser.close()
            return None, "Cookies expirados! Rode save_cookies.py novamente na sua maquina."

        # Find the file input and upload
        print("  Enviando arquivo de video...")
        
        # TikTok upload page has an iframe — we need to find the file input
        # Try multiple selectors for the file input
        file_input = None
        selectors = [
            'input[type="file"]',
            'iframe',
        ]
        
        # Check for iframe first
        iframe_element = page.query_selector('iframe')
        if iframe_element:
            frame = iframe_element.content_frame()
            if frame:
                file_input = frame.query_selector('input[type="file"]')
        
        if not file_input:
            file_input = page.query_selector('input[type="file"]')

        if not file_input:
            # Wait a bit more and try again
            time.sleep(5)
            file_input = page.query_selector('input[type="file"]')

        if not file_input:
            browser.close()
            return None, "Nao encontrou o campo de upload. Pagina pode ter mudado."

        file_input.set_input_files(video_path)
        print("  Video selecionado, aguardando processamento...")

        # Wait for upload to process (TikTok shows a progress bar)
        time.sleep(10)

        # Fill in the caption
        print("  Preenchendo legenda...")
        
        # Try to find and fill the caption editor
        # TikTok uses a contenteditable div for the caption
        caption_selectors = [
            '[data-text="true"]',
            '.public-DraftEditor-content',
            '[contenteditable="true"]',
            '.notranslate',
        ]
        
        caption_filled = False
        # Try in iframe first
        if iframe_element:
            frame = iframe_element.content_frame()
            if frame:
                for sel in caption_selectors:
                    try:
                        el = frame.query_selector(sel)
                        if el:
                            el.click()
                            # Clear existing text
                            frame.keyboard.press("Control+a")
                            frame.keyboard.type(caption, delay=20)
                            caption_filled = True
                            break
                    except:
                        continue

        if not caption_filled:
            for sel in caption_selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        el.click()
                        page.keyboard.press("Control+a")
                        page.keyboard.type(caption, delay=20)
                        caption_filled = True
                        break
                except:
                    continue

        if not caption_filled:
            print("  AVISO: Nao conseguiu preencher a legenda, postando sem.")

        # Wait for video to fully process before posting
        print("  Aguardando video processar no TikTok...")
        time.sleep(15)

        # Click the Post button
        print("  Clicando em Publicar...")
        post_selectors = [
            'button:has-text("Post")',
            'button:has-text("Publicar")',
            'button:has-text("Postar")',
            '[data-e2e="post-button"]',
        ]

        posted = False
        # Try iframe first
        if iframe_element:
            frame = iframe_element.content_frame()
            if frame:
                for sel in post_selectors:
                    try:
                        btn = frame.query_selector(sel)
                        if btn and btn.is_enabled():
                            btn.click()
                            posted = True
                            break
                    except:
                        continue

        if not posted:
            for sel in post_selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_enabled():
                        btn.click()
                        posted = True
                        break
                except:
                    continue

        if not posted:
            # Last resort: try to find any button that looks like "post"
            buttons = page.query_selector_all("button")
            for btn in buttons:
                text = btn.inner_text().lower().strip()
                if text in ["post", "publicar", "postar", "upload"]:
                    try:
                        btn.click()
                        posted = True
                        break
                    except:
                        continue

        if not posted:
            browser.close()
            return None, "Nao encontrou o botao de publicar."

        # Wait for confirmation
        print("  Aguardando confirmacao...")
        time.sleep(10)

        browser.close()

    return "browser_upload_ok", None


def determine_jobs_to_run():
    # 1. Check FORCE_POST first (manual "Postar Agora")
    force_posts = turso_query("SELECT * FROM video_posts WHERE status='FORCE_POST' ORDER BY created_at ASC LIMIT 1")
    if force_posts:
        post = force_posts[0]
        user_info = turso_query("SELECT access_token FROM users WHERE id=?", [post["user_id"]])
        if user_info:
            return {
                "post_id": post["id"],
                "user_id": post["user_id"],
                "source_url": post["source_url"],
                "caption": post["caption"],
            }

    now = datetime.now(timezone.utc)
    hour = now.hour

    pending_posts = turso_query("SELECT * FROM video_posts WHERE status='PENDING' ORDER BY created_at ASC LIMIT 100")
    if not pending_posts:
        return None

    user_next_post = {}
    for p in pending_posts:
        if p["user_id"] not in user_next_post:
            user_next_post[p["user_id"]] = p

    for user_id, post in user_next_post.items():
        cfg = turso_query("SELECT * FROM schedule_configs WHERE user_id=?", [user_id])
        if not cfg:
            cfg = {"posts_per_day": 1, "start_hour": 8, "end_hour": 22, "auto_delete": 1}
        else:
            cfg = cfg[0]

        start_h = int(cfg.get("start_hour") or 8)
        end_h = int(cfg.get("end_hour") or 22)
        posts_per_day = int(cfg.get("posts_per_day") or 1)

        if not (start_h <= hour <= end_h):
            continue

        today_str = now.strftime('%Y-%m-%d')
        published_today = turso_query(
            "SELECT id, published_at FROM video_posts WHERE user_id=? AND status='PUBLISHED' AND published_at LIKE ?",
            [user_id, f"{today_str}%"]
        )

        count_today = len(published_today)
        if count_today >= posts_per_day:
            continue

        if count_today > 0:
            published_today.sort(key=lambda x: x["published_at"] or "", reverse=True)
            last_pub = datetime.fromisoformat(published_today[0]["published_at"])
            window_hours = end_h - start_h
            if window_hours <= 0: window_hours = 1
            interval_hours = window_hours / posts_per_day
            if (now - last_pub).total_seconds() < interval_hours * 3600:
                continue

        return {
            "post_id": post["id"],
            "user_id": post["user_id"],
            "source_url": post["source_url"],
            "caption": post["caption"],
        }
    return None


def process_job(job):
    post_id    = job["post_id"]
    user_id    = job["user_id"]
    source_url = job["source_url"]
    caption    = job["caption"]

    # Get browser cookies for this user
    cookie_row = turso_query("SELECT cookies_json FROM browser_cookies WHERE user_id=?", [user_id])
    if not cookie_row or not cookie_row[0].get("cookies_json"):
        print(f"  SEM COOKIES para user {user_id}. Rode save_cookies.py primeiro!")
        turso_execute("UPDATE video_posts SET status='FAILED', error_msg=? WHERE id=?",
                      ["Cookies nao configurados. Rode: python save_cookies.py " + user_id, post_id])
        return

    cookies_json = cookie_row[0]["cookies_json"]

    print(f"\n▶ Processando: {caption}")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        try:
            print("  ⬇ Baixando video...")
            turso_execute("UPDATE video_posts SET status='DOWNLOADING' WHERE id=?", [post_id])
            download_video(source_url, video_path)

            if not os.path.exists(video_path):
                raise Exception("Download falhou - arquivo nao encontrado")

            file_size = os.path.getsize(video_path)
            print(f"  ✓ Download OK ({file_size / 1024 / 1024:.1f} MB)")

            print("  ⬆ Enviando para TikTok via browser...")
            turso_execute("UPDATE video_posts SET status='UPLOADING' WHERE id=?", [post_id])
            publish_id, error = upload_via_browser(video_path, caption, cookies_json)

            if error:
                print(f"  ✗ Erro: {error}")
                turso_execute("UPDATE video_posts SET status='FAILED', error_msg=? WHERE id=?",
                              [str(error), post_id])
            else:
                print(f"  ✓ Publicado!")
                turso_execute("UPDATE video_posts SET status='PUBLISHED', publish_id=?, published_at=? WHERE id=?",
                              [publish_id, datetime.now(timezone.utc).isoformat(), post_id])

        except Exception as e:
            print(f"  ✗ Erro: {e}")
            turso_execute("UPDATE video_posts SET status='FAILED', error_msg=? WHERE id=?",
                          [str(e), post_id])


print("🚀 Worker CrossPoster v2 (Browser Automation) — aguardando jobs...")

while True:
    try:
        job = determine_jobs_to_run()
        if job:
            process_job(job)
        else:
            time.sleep(15)
    except Exception as e:
        print(f"Erro no loop do worker: {e}")
        time.sleep(15)