from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.init import init_db
from app.api.tasks import router
@asynccontextmanager
async def lifespan(app:FastAPI):
    await init_db(); yield
app=FastAPI(title="RepoPilot",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:4200"],allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
@app.get("/health")
async def health(): return {"status":"ok"}
