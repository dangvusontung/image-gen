import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routes import assets, projects, providers
from app.schemas import HealthResponse

app = FastAPI(
    title="Character Studio API",
    description="Transform photos into stylized 3D characters",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(assets.router)
app.include_router(providers.router)


@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "message": "Character Studio API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", 8000)))
