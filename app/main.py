from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from app.routers import projects
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from contextlib import asynccontextmanager

from app.database import check_and_create_tables

import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting up application...")
    check_and_create_tables()
    yield
    # 关闭时执行（如果需要的话）
    logger.info("Shutting down application...")

app = FastAPI(
    title="NextPoints_API",
    description="NextPoints API for managing data import and annotation tasks",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)



templates = Jinja2Templates(directory="templates")

# 挂载所有静态目录
app.mount("/static", StaticFiles(directory="public"), name="static")


app.include_router(projects.router, prefix="/api/projects", tags=["projects"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/view", response_class=HTMLResponse)
async def view(request: Request):
    return templates.TemplateResponse("view.html", {"request": request})

