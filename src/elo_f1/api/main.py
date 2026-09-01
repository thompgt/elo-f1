from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from elo_f1.api.routers import drivers, seasons, standings

app = FastAPI(title="elo-f1 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(seasons.router)
app.include_router(standings.router)
app.include_router(drivers.router)
