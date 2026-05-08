import os, time, tempfile, httpx, math
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

import yt_dlp
from db.database import turso_query, turso_execute

CLIENT_ID     = os.getenv("TIKTOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

def download_video(url, output_path):
    ydl_opts = {
        "outtmpl": output_path,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def upload_to_tiktok(video_path, access_token, caption):
    file_size = os.path.getsize(video_path)

    # TikTok requires chunk_size between 5MB and 64MB
    # For small files (<= 5MB), use the file size itself as the chunk size
    MIN_CHUNK = 5 * 1024 * 1024   # 5 MB
    MAX_CHUNK = 64 * 1024 * 1024  # 64 MB

    if file_size <= MIN_CHUNK:
        # Single-chunk upload: chunk_size == file_size
        chunk_size = file_size
    else:
        chunk_size = min(10 * 1024 * 1024, MAX_CHUNK)  # 10 MB preferred

    total_chunks = math.ceil(file_size / chunk_size)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Init — declare EXACTLY what we will send
    init_resp = httpx.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title": caption,
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        },
        timeout=30,
    ).json()

    print(f"Init response: {init_resp}")

    if "data" not in init_resp:
        err = init_resp.get("error", {})
        return None, err.get("message") or str(init_resp)

    publish_id = init_resp["data"]["publish_id"]
    upload_url = init_resp["data"]["upload_url"]

    # Upload chunks — each chunk must be exactly chunk_size except the last
    with open(video_path, "rb") as f:
        chunk_index = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            start = chunk_index * chunk_size
            end   = start + len(chunk) - 1
            resp = httpx.put(
                upload_url,
                content=chunk,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Type":  "video/mp4",
                },
                timeout=120,
            )
            print(f"Chunk {chunk_index+1}/{total_chunks} enviado — status {resp.status_code}")
            chunk_index += 1

    return publish_id, None

def determine_jobs_to_run():
    # 1. Verificar forçados manualment ('Postar Agora')
    force_posts = turso_query("SELECT * FROM video_posts WHERE status='FORCE_POST' ORDER BY created_at ASC LIMIT 1")
    if force_posts:
        post = force_posts[0]
        user_info = turso_query("SELECT access_token FROM users WHERE id=?", [post["user_id"]])
        if user_info:
            return {
                "post_id": post["id"],
                "source_url": post["source_url"],
                "caption": post["caption"],
                "access_token": user_info[0]["access_token"],
            }

    now = datetime.now(timezone.utc)
    hour = now.hour

    pending_posts = turso_query("SELECT * FROM video_posts WHERE status='PENDING' ORDER BY created_at ASC LIMIT 100")
    if not pending_posts: 
        return None

    # Agrupa apenas a primeira postagem PENDING de cada usuário (FIFO)
    user_next_post = {}
    for p in pending_posts:
        if p["user_id"] not in user_next_post:
            user_next_post[p["user_id"]] = p

    for user_id, post in user_next_post.items():
        # Capturar configs locais de postagem
        cfg = turso_query("SELECT * FROM schedule_configs WHERE user_id=?", [user_id])
        if not cfg:
            cfg = {"posts_per_day": 1, "start_hour": 8, "end_hour": 22, "auto_delete": 1}
        else:
            cfg = cfg[0]

        start_h = int(cfg.get("start_hour") or 8)
        end_h = int(cfg.get("end_hour") or 22)
        posts_per_day = int(cfg.get("posts_per_day") or 1)
        
        # O post so entra pra avaliação se estivermos na janela diária pretendida
        if not (start_h <= hour <= end_h):
            continue 
        
        # Checar se ja atingiu a cota diária
        today_str = now.strftime('%Y-%m-%d')
        published_today = turso_query(
            "SELECT id, published_at FROM video_posts WHERE user_id=? AND status='PUBLISHED' AND published_at LIKE ?", 
            [user_id, f"{today_str}%"]
        )
        
        count_today = len(published_today)
        if count_today >= posts_per_day:
            continue # Limite diário excedido

        if count_today > 0:
            # Verifica intervalo minimizado com relacao ao horario util
            published_today.sort(key=lambda x: x["published_at"], reverse=True)
            last_pub = datetime.fromisoformat(published_today[0]["published_at"])
            
            window_hours = end_h - start_h
            if window_hours <= 0: window_hours = 1
            interval_hours = window_hours / posts_per_day
            
            if (now - last_pub).total_seconds() < interval_hours * 3600:
                continue # Ainda precisa de delay antes de postar

        # Caso cumpra todas as regras de timing, enviar este item.
        user_info = turso_query("SELECT access_token FROM users WHERE id=?", [user_id])
        if not user_info:
            continue
            
        return {
            "post_id": post["id"],
            "source_url": post["source_url"],
            "caption": post["caption"],
            "access_token": user_info[0]["access_token"],
        }
    return None

def process_job(job):
    post_id     = job["post_id"]
    source_url  = job["source_url"]
    caption     = job["caption"]
    access_token= job["access_token"]

    print(f"\\n▶ Processando: {caption}")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        try:
            print("⬇ Baixando vídeo...")
            turso_execute("UPDATE video_posts SET status='DOWNLOADING' WHERE id=?", [post_id])
            download_video(source_url, video_path)
            print("✓ Download concluído")

            print("⬆ Enviando para TikTok...")
            turso_execute("UPDATE video_posts SET status='UPLOADING' WHERE id=?", [post_id])
            publish_id, error = upload_to_tiktok(video_path, access_token, caption)

            if error:
                print(f"✗ Erro no upload: {error}")
                turso_execute("UPDATE video_posts SET status='FAILED', error_msg=? WHERE id=?", [str(error), post_id])
            else:
                print(f"✓ Publicado! publish_id: {publish_id}")
                turso_execute("UPDATE video_posts SET status='PUBLISHED', publish_id=?, published_at=? WHERE id=?", 
                              [publish_id, datetime.now(timezone.utc).isoformat(), post_id])

        except Exception as e:
            print(f"✗ Erro: {e}")
            turso_execute("UPDATE video_posts SET status='FAILED', error_msg=? WHERE id=?", [str(e), post_id])

print("🚀 Worker do CrossPoster reconfigurado para Agendamento — aguardando jobs...")

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