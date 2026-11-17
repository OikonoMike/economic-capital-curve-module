from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.curves_api.routers.curves import router as curves_router
from src.curves_api.routers.runs import router as runs_router

app = FastAPI(
    title="Economic Capital Curves API",
    description="API для получения кривых процентных ставок",
    version="1.0.0",
)

# CORS — разрешение запросов от фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Только для локальной разработки
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(curves_router)
app.include_router(runs_router)