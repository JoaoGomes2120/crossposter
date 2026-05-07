import redis, os
from dotenv import load_dotenv
load_dotenv()

r = redis.from_url(os.getenv('REDIS_URL'))
print('Jobs na fila:', r.llen('crossposter:queue'))
job = r.lindex('crossposter:queue', 0)
print('Primeiro job:', job)