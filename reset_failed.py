from db.database import turso_execute, turso_query

# show current state
posts = turso_query("SELECT caption, status, error_msg FROM video_posts")
for p in posts:
    print(p)

# reset FAILED back to PENDING
turso_execute("UPDATE video_posts SET status='PENDING', error_msg='' WHERE status='FAILED'")
print("\n✅ Todos os FAILED resetados para PENDING")
