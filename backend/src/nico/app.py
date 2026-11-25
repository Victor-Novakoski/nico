from fastapi import Depends, FastAPI

from nico.auth import current_user
from nico.db import lifespan
from nico.routes import payment_methods, people, session, settings

app = FastAPI(title="Nico", lifespan=lifespan)

# Toda rota nova de dados entra assim: app.include_router(x.router, dependencies=PROTECTED).
# Só /api/health e /api/login ficam abertas (um teste confere isso).
PROTECTED = [Depends(current_user)]


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


# Login é aberto; logout e /me exigem login por conta própria.
app.include_router(session.router)
app.include_router(people.router, dependencies=PROTECTED)
app.include_router(payment_methods.router, dependencies=PROTECTED)
app.include_router(settings.router, dependencies=PROTECTED)
