from fastapi import FastAPI

from app.api.tasks import router as tasks_router

app = FastAPI(
    title="AWS Task Board",
    description="Task board API backend on PostgreSQL in AWS RDS",
    version="0.1.0",
)

app.include_router(tasks_router)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"status": "ok", "message": "AWS Task Board API is running"}
