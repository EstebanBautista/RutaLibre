"""Request and response models. Pydantic validates them and FastAPI turns
them into the OpenAPI documentation served at /docs."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine import MAX_STOPS

# allow_inf_nan=False rejects NaN and Infinity, which would poison every distance.
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False, description="Latitud en grados")]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False, description="Longitud en grados")]


class Depot(BaseModel):
    lat: Latitude
    lng: Longitude


class Stop(BaseModel):
    id: int = Field(description="Identificador de la parada; se devuelve en el orden optimizado")
    lat: Latitude
    lng: Longitude


class OptimizeRequest(BaseModel):
    depot: Depot = Field(description="Punto de salida y de regreso")
    stops: list[Stop] = Field(min_length=1, max_length=MAX_STOPS, description="Entre 1 y 100 paradas")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "depot": {"lat": 3.4516, "lng": -76.5320},
                "stops": [
                    {"id": 1, "lat": 3.4490, "lng": -76.5400},
                    {"id": 2, "lat": 3.3730, "lng": -76.5390},
                    {"id": 3, "lat": 3.4600, "lng": -76.5290},
                ],
            }
        }
    )

    @model_validator(mode="after")
    def stop_ids_are_unique(self) -> "OptimizeRequest":
        ids = [stop.id for stop in self.stops]
        if len(ids) != len(set(ids)):
            raise ValueError("los ids de las paradas deben ser únicos")
        return self


class OptimizeResponse(BaseModel):
    order: list[int] = Field(description="Ids de las paradas en el orden de visita")
    optimized_km: float = Field(description="Longitud del circuito optimizado, en km")
    naive_km: float = Field(description="Longitud del circuito en el orden recibido, en km")
    stops_count: int


class Health(BaseModel):
    status: str
    engine: str
