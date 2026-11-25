from fastapi import FastAPI

from nico.db import lifespan
from nico.routes import people

app = FastAPI(title="Nico", lifespan=lifespan)
app.include_router(people.router)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
