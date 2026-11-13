"""HTTP client for the optimizer service (FastAPI + C++ engine).

Anything that goes wrong on the way (network, timeout, an error status, or an
answer that is not a valid route) is reported as OptimizerUnavailable, so the
caller has a single failure to handle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx
from django.conf import settings

# Tests replace this with httpx.MockTransport to fake the network.
_transport: httpx.BaseTransport | None = None


class OptimizerUnavailable(Exception):
    pass


@dataclass(frozen=True)
class OptimizerResult:
    order: list[int]  # stop ids in visit order
    optimized_km: float
    naive_km: float


def optimize_route(depot: tuple[float, float], stops: list[dict], token: str) -> OptimizerResult:
    """Asks the optimizer for the best visiting order.

    stops is a list of {"id", "lat", "lng"}. token is the caller's JWT, which
    the optimizer verifies with the signing key it shares with this backend.
    """
    payload = {"depot": {"lat": depot[0], "lng": depot[1]}, "stops": stops}
    try:
        with httpx.Client(timeout=settings.OPTIMIZER_TIMEOUT_SECONDS, transport=_transport) as client:
            response = client.post(
                f"{settings.OPTIMIZER_URL}/optimize",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as exc:
        raise OptimizerUnavailable(f"request failed: {exc!r}") from exc

    if response.status_code != 200:
        raise OptimizerUnavailable(f"unexpected status {response.status_code}")

    try:
        data = response.json()
        order = [int(stop_id) for stop_id in data["order"]]
        optimized_km = float(data["optimized_km"])
        naive_km = float(data["naive_km"])
    except (ValueError, KeyError, TypeError) as exc:
        raise OptimizerUnavailable("malformed response") from exc

    # Never trust the answer blindly: it must be exactly the ids we sent.
    sent_ids = [stop["id"] for stop in stops]
    if len(order) != len(sent_ids) or sorted(order) != sorted(sent_ids):
        raise OptimizerUnavailable("response is not a permutation of the stops sent")
    if not (math.isfinite(optimized_km) and math.isfinite(naive_km)) or optimized_km < 0 or naive_km < 0:
        raise OptimizerUnavailable("response distances are not valid")

    return OptimizerResult(order=order, optimized_km=optimized_km, naive_km=naive_km)
