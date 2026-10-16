import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo.errors import PyMongoError
from app.core.config import ROOT, Settings
from app.core.database import connect, ensure_indexes
from app.routers import auth, management, responses, statistics, surveys

def create_app(settings: Settings | None = None, database=None) -> FastAPI:
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        client = None
        try:
            if database is None:
                client = connect(settings)
                app.state.db = client[settings.mongodb_database]
            else:
                app.state.db = database
            ensure_indexes(app.state.db)
            yield
        finally:
            if client is not None:
                client.close()
    app = FastAPI(title='MongoDB 问卷系统 · 第一阶段', lifespan=lifespan)
    app.state.settings = settings
    app.include_router(auth.router)
    app.include_router(surveys.router)
    app.include_router(responses.router)
    app.include_router(statistics.router)
    app.include_router(management.router)
    app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')
    templates = Jinja2Templates(directory=ROOT / 'app/templates')
    @app.exception_handler(PyMongoError)
    async def database_error(request, exc):
        logging.getLogger(__name__).exception('MongoDB request failed', exc_info=exc)
        return JSONResponse(status_code=503, content={'detail': '数据库暂时不可用'})
    @app.get('/', include_in_schema=False)
    def home(request: Request):
        return templates.TemplateResponse(request=request, name='index.html')
    @app.get('/health')
    def health(request: Request):
        request.app.state.db.command('ping')
        return {'status': 'ok'}
    return app

app = create_app()
