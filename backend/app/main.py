from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="PromptForge AI")

app.include_router(router)

@app.get("/")
def home():
    return {
        "message": "PromptForge AI Backend Running"
    }