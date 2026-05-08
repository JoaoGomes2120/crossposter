from db.database import turso_query
res = turso_query("SELECT error_msg FROM video_posts WHERE status='FAILED' ORDER BY id DESC LIMIT 1")
print("ERRO DO BANCO:", res[0]['error_msg'] if res else "Nenhum erro encontrado")
