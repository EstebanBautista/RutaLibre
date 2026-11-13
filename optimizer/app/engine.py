"""Loads engine.wasm (the C++ route engine) and calls it from Python.

The module exposes two static buffers in its linear memory:

    rl_coords() -> doubles  [depot_lat, depot_lng, stop0_lat, stop0_lng, ...]
    rl_order()  -> int32    stop indices in visit order, written by rl_optimize

So a call is: write the coordinates, run rl_optimize(n), read n integers back.
"""

from __future__ import annotations

import struct
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import wasmtime

WASM_PATH = Path(__file__).resolve().parent / "engine.wasm"
MAX_STOPS = 100

Point = tuple[float, float]  # (lat, lng)


@dataclass(frozen=True)
class EngineResult:
    order: list[int]  # indices into the stops list, in visit order
    optimized_km: float
    naive_km: float  # length when visiting the stops in the order received


class Engine:
    def __init__(self, wasm_path: Path = WASM_PATH) -> None:
        engine = wasmtime.Engine()
        module = wasmtime.Module.from_file(engine, str(wasm_path))
        self._store = wasmtime.Store(engine)

        # The engine is built without imports. If a future build pulls in WASI
        # functions, link them so the module still loads.
        linker = wasmtime.Linker(engine)
        if any(imp.module == "wasi_snapshot_preview1" for imp in module.imports):
            linker.define_wasi()
            self._store.set_wasi(wasmtime.WasiConfig())
        instance = linker.instantiate(self._store, module)
        exports = instance.exports(self._store)

        # Standalone Emscripten modules export _initialize to run static setup.
        initialize = exports.get("_initialize")
        if initialize is not None:
            initialize(self._store)

        self._memory = exports["memory"]
        self._rl_naive_km = exports["rl_naive_km"]
        self._rl_optimize = exports["rl_optimize"]
        self._coords_ptr = exports["rl_coords"](self._store)
        self._order_ptr = exports["rl_order"](self._store)

        # A wasmtime Store must not be used from two threads at once, and the
        # engine keeps its working data in static buffers.
        self._lock = threading.Lock()

    def optimize(self, depot: Point, stops: list[Point]) -> EngineResult:
        n = len(stops)
        if n > MAX_STOPS:
            raise ValueError(f"at most {MAX_STOPS} stops are supported, got {n}")
        if n == 0:
            return EngineResult(order=[], optimized_km=0.0, naive_km=0.0)

        flat = [depot[0], depot[1]]
        for lat, lng in stops:
            flat.extend((lat, lng))
        coords_bytes = struct.pack(f"<{len(flat)}d", *flat)  # little-endian doubles

        with self._lock:
            self._memory.write(self._store, coords_bytes, self._coords_ptr)
            naive_km = self._rl_naive_km(self._store, n)
            optimized_km = self._rl_optimize(self._store, n)
            order_bytes = self._memory.read(self._store, self._order_ptr, self._order_ptr + 4 * n)

        order = list(struct.unpack(f"<{n}i", order_bytes))
        return EngineResult(order=order, optimized_km=optimized_km, naive_km=naive_km)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """One engine per process: compiling the module is the expensive part."""
    return Engine()
