from fastapi import FastAPI

from nico.db import lifespan

app = FastAPI(title="Nico", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
