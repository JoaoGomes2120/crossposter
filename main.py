from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "online", "app": "CrossPoster"}

@app.get("/health")
def health():
    return {"healthy": True}