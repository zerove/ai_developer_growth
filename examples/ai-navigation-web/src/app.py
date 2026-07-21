from fastapi import FastAPI
from contextlib import asynccontextmanager

from .database import init_db
from .routes.auth_routes import router as auth_router
from .routes.dashboard_routes import router as dashboard_router
from .routes.assess_routes import router as assess_router
from .routes.progress_routes import router as progress_router
from .routes.contribute_routes import router as contribute_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="AI Developer Growth", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(assess_router)
app.include_router(progress_router)
app.include_router(contribute_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
