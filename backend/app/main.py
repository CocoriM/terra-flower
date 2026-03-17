from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import auth, globe, health, moderation, plants, uploads
from app.services.storage import LOCAL_STORAGE_ROOT

app = FastAPI(title="TerraFlora API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(plants.router, prefix="/api/plants", tags=["plants"])
app.include_router(globe.router, prefix="/api/globe", tags=["globe"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(moderation.router, prefix="/api/moderation", tags=["moderation"])
app.include_router(health.router, prefix="/api", tags=["health"])

LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=LOCAL_STORAGE_ROOT), name="media")
