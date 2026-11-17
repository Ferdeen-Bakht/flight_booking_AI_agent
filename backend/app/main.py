from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect

from .config import settings
from .db import Base, engine
from .routers import api, auth, payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: the booking schema changed (offers/passengers snapshot). If an old-layout
    # database is found, rebuild the tables instead of crashing. This wipes old users/bookings.
    insp = inspect(engine)
    if insp.has_table("bookings") and "offer_json" not in {c["name"] for c in insp.get_columns("bookings")}:
        print("[startup] old database layout detected - recreating tables")
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS bookings")
            conn.exec_driver_sql("DROP TABLE IF EXISTS payments")
            conn.exec_driver_sql("DROP TABLE IF EXISTS users")
            conn.exec_driver_sql("DROP TABLE IF EXISTS flights")
    Base.metadata.create_all(engine)
    print(f"[startup] flight provider: {settings.provider}")
    yield


app = FastAPI(title="Flight Booking Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[settings.frontend_url, "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(api.router)
app.include_router(payments.router)


@app.get("/api/health")
def health():
    return {"ok": True, "model": settings.ollama_model}
