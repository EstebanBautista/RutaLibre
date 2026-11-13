"""Build script for the RutaLibre route engine.

Usage (run from anywhere, with emcc on PATH or emsdk under .tools/emsdk):

    python engine/build.py          # compile engine.wasm and copy it to the apps
    python engine/build.py --test   # compile the C++ tests to wasm and run them with Node

The compiled engine.wasm is committed to the repository so that the hosting
platform never needs a C++ toolchain.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = ENGINE_DIR.parent
BUILD_DIR = ENGINE_DIR / "build"
SOURCES = [ENGINE_DIR / "src" / "route.cpp"]
WASM_API = ENGINE_DIR / "src" / "wasm_api.cpp"
TEST_SOURCE = ENGINE_DIR / "tests" / "test_route.cpp"

# Functions the WebAssembly module exposes to its hosts (browser and Python).
EXPORTS = ["rl_coords", "rl_order", "rl_haversine_km", "rl_naive_km", "rl_optimize"]

# Every place that ships a copy of the compiled engine.
WASM_TARGETS = [
    REPO_ROOT / "optimizer" / "app" / "engine.wasm",
    REPO_ROOT / "frontend" / "wasm" / "engine.wasm",
]

COMMON_FLAGS = ["-std=c++17", "-O2", f"-I{ENGINE_DIR / 'include'}"]


def find_emcc() -> str:
    """Returns the emcc executable, preferring PATH, then the local emsdk."""
    found = shutil.which("emcc")
    if found:
        return found
    emsdk = REPO_ROOT / ".tools" / "emsdk"
    for name in ("emcc.exe", "emcc.bat", "emcc"):
        local = emsdk / "upstream" / "emscripten" / name
        if local.exists():
            # Point Emscripten at the configuration emsdk generated on activate.
            os.environ.setdefault("EM_CONFIG", str(emsdk / ".emscripten"))
            return str(local)
    sys.exit("emcc not found. Install emsdk (see README) or add emcc to PATH.")


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def build_wasm() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    output = BUILD_DIR / "engine.wasm"
    run(
        [
            find_emcc(),
            *COMMON_FLAGS,
            "-fno-exceptions",
            "-fno-rtti",
            "--no-entry",  # a library, not a program: there is no main()
            "-sSTANDALONE_WASM=1",  # no JavaScript glue; usable outside the browser
            "-sALLOW_MEMORY_GROWTH=0",
            "-sEXPORTED_FUNCTIONS=" + ",".join("_" + name for name in EXPORTS),
            *SOURCES,
            WASM_API,
            "-o",
            output,
        ]
    )
    for target in WASM_TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output, target)
        print(f"copied -> {target.relative_to(REPO_ROOT)}")


def run_tests() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    output = BUILD_DIR / "test_route.js"
    run([find_emcc(), *COMMON_FLAGS, *SOURCES, TEST_SOURCE, "-o", output])
    run(["node", output])


if __name__ == "__main__":
    if "--test" in sys.argv[1:]:
        run_tests()
    else:
        build_wasm()
