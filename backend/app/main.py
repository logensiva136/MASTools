from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import apps, auth, controls, projects, reports, test_runs

settings = get_settings()

app = FastAPI(title="MASTools API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(apps.router)
app.include_router(controls.router)
app.include_router(test_runs.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}
