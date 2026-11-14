"""RutaLibre optimizer: a small FastAPI service around the C++ route engine."""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import require_user
from app.engine import get_engine
from app.schemas import Health, OptimizeRequest, OptimizeResponse

app = FastAPI(
    title="RutaLibre · Optimizador de rutas",
    version="0.1.0",
    description=(
        "Calcula el orden de visita más corto para un conjunto de entregas. "
        "El cálculo lo hace un motor escrito en C++ (vecino más cercano + 2-opt) "
        "compilado a WebAssembly y ejecutado con wasmtime. "
        "Las distancias son en línea recta (haversine) y el recorrido sale del "
        "depósito y vuelve a él."
    ),
)

_origins = [origin.strip() for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
if not _origins and os.environ.get("VERCEL") != "1":
    _origins = ["http://localhost:5500", "http://127.0.0.1:5500"]  # local default
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Same 422 shape as FastAPI's default, without echoing the rejected input.

    The default handler copies the offending value into the response. When
    that value is NaN the response itself cannot be encoded as JSON and the
    client would get a 500 instead of a validation error.
    """
    errors = [
        {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health", response_model=Health, summary="Estado del servicio", tags=["servicio"])
def health() -> Health:
    get_engine()  # fails loudly here if engine.wasm is missing from the deployment
    return Health(status="ok", engine="wasm")


@app.post(
    "/optimize",
    response_model=OptimizeResponse,
    summary="Optimiza el orden de las paradas",
    tags=["rutas"],
    responses={401: {"description": "Token ausente, inválido o vencido"}},
)
def optimize(request: OptimizeRequest, _claims: dict = Depends(require_user)) -> OptimizeResponse:
    result = get_engine().optimize(
        (request.depot.lat, request.depot.lng),
        [(stop.lat, stop.lng) for stop in request.stops],
    )
    return OptimizeResponse(
        order=[request.stops[index].id for index in result.order],
        optimized_km=round(result.optimized_km, 3),
        naive_km=round(result.naive_km, 3),
        stops_count=len(request.stops),
    )
