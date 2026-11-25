from fastapi import FastAPI

app = FastAPI(title="Nico")


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
