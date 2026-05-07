import os, time, sqlite3, tempfile, httpx, math
from dotenv import load_dotenv
load_dotenv()

import redis
import yt_dlp

REDIS_URL     = os.getenv("REDIS_URL")
CLIENT_ID     = os.getenv("TIKTOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

DB_PATH = "crossposter.db"  # banco local para testes

r = redis.from_url(REDIS_URL)

def get_next_job():
    job = r.lpop("crossposter:queue")
    return job

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
    chunk_size = 10_000_000
    total_chunks = math.ceil(file_size / chunk_size)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Init
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
    ).json()

    print(f"Init response: {init_resp}")

    if "data" not in init_resp:
        return None, init_resp.get("error", {}).get("message", "erro desconhecido")

    publish_id = init_resp["data"]["publish_id"]
    upload_url = init_resp["data"]["upload_url"]

    # Upload chunks
    with open(video_path, "rb") as f:
        chunk_index = 0
        while chunk := f.read(chunk_size):
            start = chunk_index * chunk_size
            end   = start + len(chunk) - 1
            httpx.put(
                upload_url,
                content=chunk,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Type":  "video/mp4",
                },
            )
            print(f"Chunk {chunk_index+1}/{total_chunks} enviado")
            chunk_index += 1

    return publish_id, None

def process_job(job_data):
    import json
    job = json.loads(job_data)
    post_id     = job["post_id"]
    source_url  = job["source_url"]
    caption     = job["caption"]
    access_token= job["access_token"]

    print(f"\n▶ Processando: {caption}")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        try:
            print("⬇ Baixando vídeo...")
            download_video(source_url, video_path)
            print("✓ Download concluído")

            print("⬆ Enviando para TikTok...")
            publish_id, error = upload_to_tiktok(video_path, access_token, caption)

            if error:
                print(f"✗ Erro no upload: {error}")
            else:
                print(f"✓ Publicado! publish_id: {publish_id}")

        except Exception as e:
            print(f"✗ Erro: {e}")

print("🚀 Worker iniciado — aguardando jobs...")
print(f"Conectado ao Redis: {REDIS_URL[:30]}...")

while True:
    job = get_next_job()
    if job:
        process_job(job)
    else:
        time.sleep(5)  # espera 5s e verifica novamente