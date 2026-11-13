# RutaLibre MVP — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar hoy desplegado y público RutaLibre: planificador de entregas con backend Django + DRF, optimizador FastAPI, motor C++ en WebAssembly y frontend AngularJS, con costo $0.

**Architecture:** Monorepo con cuatro piezas. El motor C++ se compila a un único `engine.wasm` que corre en el navegador (vista previa instantánea) y dentro de FastAPI con `wasmtime` (cálculo autoritativo). Django es la API principal, guarda todo en Postgres (Neon) y llama al optimizador al crear una ruta. Tres proyectos de Vercel sirven backend, optimizador y frontend.

**Tech Stack:** C++17 + Emscripten (emsdk), Python 3.12, Django 5.2 LTS, Django REST Framework, simplejwt, FastAPI, Pydantic v2, wasmtime, AngularJS 1.8.3, angular-route 1.8.3, Leaflet 1.9.4, Neon Postgres, Vercel, GitHub Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-rutalibre-design.md`

## Global Constraints

- Raíz del proyecto: `I:\proyecto_trabajo`. Entornos virtuales, emsdk y cualquier descarga pesada van dentro de esa carpeta. Nada pesado en C:.
- Costo $0. Sin AWS real. Sin servicios que pausen por inactividad.
- El desarrollo local no depende de Docker.
- No se compila el motor con el `g++` local (MinGW 6.3). Solo con `emcc` de emsdk; nativo solo en CI.
- Ningún secreto en el repo. Cada servicio tiene `.env.example`.
- Código e identificadores en inglés. Interfaz, README y documentación en español.
- Máximo 100 paradas por ruta (`RL_MAX_STOPS = 100`).
- La ruta es un circuito: depósito → paradas → depósito. Distancias haversine en km, radio terrestre `6371.0088`.
- JWT HS256. Django firma y FastAPI verifica con la misma variable `JWT_SIGNING_KEY`.
- El README nunca presenta como hecho algo que el demo no hace.
- Se trabaja directo sobre `main` (un solo desarrollador, entrega hoy). Un commit por tarea como mínimo.
- Zona horaria `America/Bogota`, idioma `es-co`.

## Review Focus

1. **Ids de pedidos inválidos al crear ruta** (lista vacía, repetidos, de otro negocio, ya asignados): respuesta 400 y ningún dato guardado. Test en Tarea 6.
2. **Coordenadas raras** (fuera de rango, `NaN`, todas las paradas en el mismo punto, n = 0 o n = 101): el motor no se cuelga ni devuelve `NaN`; la API responde 422. Tests en Tareas 2 y 3.
3. **Doble clic** en "Marcar entregado" o en "Confirmar ruta": entregar es idempotente; el segundo intento de crear la misma ruta responde 400 y no duplica. Tests en Tarea 6.
4. **Optimizador lento o caído** (arranque en frío): Django responde 502 con mensaje claro, sin datos a medias; el frontend muestra el mensaje y permite reintentar. Test en Tarea 6, verificación manual en Tarea 8.
5. **Token vencido o inválido en el navegador**: el interceptor borra la sesión y lleva al login, sin pantalla en blanco. Verificación manual en Tarea 7.
6. **Demo ensuciado por visitantes**: tope de 200 pedidos por negocio (400 al superarlo) y botón de restablecer. Test en Tarea 5 y Tarea 6.

## Estructura de archivos

```
.gitignore  README.md
engine/
  include/rutalibre.h        API C exportada al wasm
  src/route.hpp, route.cpp   Algoritmos (haversine, vecino más cercano, 2-opt)
  src/wasm_api.cpp           Buffers estáticos + funciones extern "C"
  tests/test_route.cpp       Tests con asserts
  CMakeLists.txt             Build nativo de tests (CI)
  build.py                   Compila con emcc, copia el wasm, corre tests
optimizer/
  pyproject.toml  .env.example
  app/main.py                FastAPI: /optimize, /health, CORS
  app/schemas.py             Modelos Pydantic
  app/engine.py              Carga y llama engine.wasm con wasmtime
  app/auth.py                Verificación del JWT
  app/engine.wasm            Artefacto versionado
  tests/test_engine.py, test_api.py
backend/
  pyproject.toml  manage.py  .env.example
  config/settings.py, urls.py, wsgi.py
  core/models.py, serializers.py, views.py, urls.py, permissions.py, admin.py
  core/demo.py               Datos demo: crear y restablecer
  core/optimizer_client.py   Cliente HTTP del optimizador
  core/management/commands/seed_demo.py
  tests/conftest.py, test_auth.py, test_orders.py, test_routes.py
frontend/
  index.html  css/app.css
  vendor/                    angular, angular-route, leaflet (archivos locales)
  wasm/engine.wasm           Artefacto versionado
  js/config.js               URLs por entorno
  js/engine-loader.js        Carga el wasm (sin Angular, testeable en Node)
  js/app.js                  Módulo, rutas, guard de sesión, interceptor
  js/services/auth.service.js, api.service.js, engine.service.js, map.service.js
  js/controllers/login, orders, planner, routes, route-detail (.controller.js)
  views/login.html, orders.html, planner.html, routes.html, route-detail.html
  tests/engine-loader.test.mjs
docs/adr/0001..0003, docs/EXPLICACION.md, docs/architecture.md
.github/workflows/ci.yml
```

---

### Task 1: Repositorio y toolchain

**Files:**
- Create: `.gitignore`, `README.md` (título y una línea; se completa en Tarea 11)

**Interfaces:**
- Produces: repo git en `I:\proyecto_trabajo` con remoto `origin` en GitHub (`EstebanBautista/rutalibre`, público); `emcc` disponible tras ejecutar `.tools\emsdk\emsdk_env.ps1`.

- [ ] **Step 1:** `git init -b main` en `I:\proyecto_trabajo`. `.gitignore` con: `.tools/`, `.venv/`, `__pycache__/`, `*.pyc`, `db.sqlite3`, `.env`, `.env.local`, `.vercel/`, `node_modules/`, `engine/build/`, `staticfiles/`.
- [ ] **Step 2:** Instalar emsdk: `git clone https://github.com/emscripten-core/emsdk.git .tools/emsdk`, luego `emsdk install latest` y `emsdk activate latest`. Anotar la versión instalada; se fija la misma en CI (Tarea 9).
- [ ] **Step 3:** Verificar: `emcc --version` imprime versión. `git status` no lista `.tools/`.
- [ ] **Step 4:** Commit de `.gitignore`, `README.md` y `docs/`. Crear el repo con `gh repo create rutalibre --public --source . --push` (confirmar con Esteban antes de publicar).

### Task 2: Motor C++ y su WebAssembly

**Files:**
- Create: `engine/include/rutalibre.h`, `engine/src/route.hpp`, `engine/src/route.cpp`, `engine/src/wasm_api.cpp`, `engine/tests/test_route.cpp`, `engine/CMakeLists.txt`, `engine/build.py`
- Create (generados y versionados): `optimizer/app/engine.wasm`, `frontend/wasm/engine.wasm`

**Interfaces:**
- Produces, C++ interno (`namespace rl`, `route.hpp`):
  ```cpp
  constexpr int kMaxStops = 100;
  double haversine_km(double lat1, double lng1, double lat2, double lng2);
  // coords: (n+1) pares lat,lng; el par 0 es el depósito. order: n índices de parada 0..n-1.
  double tour_km(const double* coords, const int* order, int n);
  // Llena order_out con el orden de visita. Devuelve km del circuito.
  double optimize(const double* coords, int n, int* order_out);
  ```
- Produces, exports del wasm (`rutalibre.h`, todas `extern "C"`):
  ```c
  double*  rl_coords(void);   // buffer estático de 2*(100+1) doubles
  int32_t* rl_order(void);    // buffer estático de 100 int32
  double   rl_haversine_km(double lat1, double lng1, double lat2, double lng2);
  double   rl_naive_km(int32_t n);   // circuito en orden 0,1,...,n-1
  double   rl_optimize(int32_t n);   // escribe rl_order(); devuelve km
  ```
  `rl_naive_km` y `rl_optimize` devuelven `-1.0` si `n < 0` o `n > 100`, y `0.0` si `n == 0`.
- Sin memoria dinámica: el núcleo usa arreglos estáticos (matriz 101×101). Así el wasm no necesita `malloc` ni imports.

- [ ] **Step 1: Tests que fallan** en `engine/tests/test_route.cpp` (macro `CHECK` propia que cuenta fallos y `main` devuelve distinto de 0 si hay alguno):
  - `haversine_km(0,0,0,0) == 0`.
  - `haversine_km(3.4516,-76.5320, 4.7110,-74.0721)` (Cali–Bogotá) entre 295 y 305 km.
  - `optimize` con n = 0 devuelve 0; con n = 1 devuelve el doble de la distancia depósito–parada y `order = {0}`.
  - Cuatro paradas en las esquinas de un cuadrado dadas en orden cruzado (0,2,1,3): `optimize` devuelve un circuito menor que `tour_km` del orden dado.
  - Diez paradas pseudoaleatorias con semilla fija: `optimize(...) <= tour_km(orden ingenuo) + 1e-9`, y `order_out` es una permutación de 0..9.
  - Cinco paradas idénticas al depósito: resultado 0, sin `NaN`, permutación válida.
  - n = 100 con semilla fija: termina y devuelve permutación válida.
- [ ] **Step 2:** `engine/build.py` con dos modos. `python engine/build.py --test`: compila tests + `route.cpp` con `emcc -std=c++17 -O2` a `engine/build/test_route.js` y lo corre con `node`. Ejecutar: debe fallar por símbolos no definidos.
- [ ] **Step 3: Implementar** `route.cpp`. Vecino más cercano desde el depósito y luego 2-opt (invertir el segmento `i..j` cuando acorta el circuito; repetir hasta una pasada sin mejora; umbral de mejora `1e-9` para garantizar terminación). Empates: gana el índice menor, para que el resultado sea determinista.
- [ ] **Step 4:** `python engine/build.py --test` → todos los tests pasan.
- [ ] **Step 5:** `wasm_api.cpp` con los buffers estáticos y los cinco exports. `python engine/build.py` (sin flag) compila:
  `emcc -std=c++17 -O2 -fno-exceptions -fno-rtti --no-entry -sSTANDALONE_WASM=1 -sALLOW_MEMORY_GROWTH=0 -sEXPORTED_FUNCTIONS=_rl_coords,_rl_order,_rl_haversine_km,_rl_naive_km,_rl_optimize -o engine/build/engine.wasm`
  y copia el resultado a `optimizer/app/engine.wasm` y `frontend/wasm/engine.wasm`.
- [ ] **Step 6: Verificar imports.** `node -e "const m=new WebAssembly.Module(require('fs').readFileSync('engine/build/engine.wasm'));console.log(WebAssembly.Module.imports(m), WebAssembly.Module.exports(m).map(e=>e.name))"`. Esperado: lista de imports vacía y los cinco `rl_*` en exports. Si aparecen imports de `wasi_snapshot_preview1`, anotarlos: las Tareas 3 y 8 ya los cubren (WASI en wasmtime, stubs en navegador).
- [ ] **Step 7:** `CMakeLists.txt` mínimo: librería `rutalibre_core`, ejecutable `test_route`, `enable_testing()` + `add_test`. No se corre en local; lo usa el CI.
- [ ] **Step 8:** Commit.

### Task 3: Optimizador FastAPI

**Files:**
- Create: `optimizer/pyproject.toml`, `optimizer/.env.example`, `optimizer/app/__init__.py`, `app/main.py`, `app/schemas.py`, `app/engine.py`, `app/auth.py`, `optimizer/tests/test_engine.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: exports de `engine.wasm` (Tarea 2).
- Produces:
  - `app/engine.py`: `class Engine` con `optimize(depot: tuple[float, float], stops: list[tuple[float, float]]) -> EngineResult`; `EngineResult(order: list[int], optimized_km: float, naive_km: float)` donde `order` son índices de `stops`. `get_engine() -> Engine` devuelve una instancia única por proceso. Las llamadas al wasm van bajo un `threading.Lock` (el `Store` de wasmtime no es seguro entre hilos).
  - `app/auth.py`: dependencia `require_user(...) -> dict` que lee `Authorization: Bearer`, verifica HS256 con `JWT_SIGNING_KEY`, exige `token_type == "access"` y expiración válida; si no, 401.
  - HTTP `POST /optimize`:
    - Entrada: `{"depot": {"lat": float, "lng": float}, "stops": [{"id": int, "lat": float, "lng": float}, ...]}`
    - Salida 200: `{"order": [id, ...], "optimized_km": float, "naive_km": float, "stops_count": int}` con km redondeados a 3 decimales.
  - HTTP `GET /health` → `{"status": "ok", "engine": "wasm"}` sin autenticación.
- Variables: `JWT_SIGNING_KEY`, `CORS_ALLOWED_ORIGINS` (lista separada por comas).
- `pyproject.toml`: `requires-python = ">=3.12"`; dependencias `fastapi`, `wasmtime`, `pyjwt`; grupo dev `pytest`, `httpx`. Entrypoint detectado por Vercel en `app/main.py` (instancia `app`).

- [ ] **Step 1:** Crear venv en `optimizer/.venv` e instalar dependencias.
- [ ] **Step 2: Tests que fallan.**
  - `test_engine.py`: cuadrado cruzado → `optimized_km < naive_km`; `order` es permutación; lista vacía de paradas → `order == []` y km 0.
  - `test_api.py` (con `TestClient` y un token creado con `pyjwt` y la clave de test):
    - sin token → 401; token con firma incorrecta → 401; token vencido → 401; token con `token_type="refresh"` → 401.
    - petición válida de 4 paradas → 200, `order` contiene exactamente los ids enviados, `optimized_km <= naive_km`, `stops_count == 4`.
    - `stops` vacío → 422; 101 paradas → 422; `lat = 91` → 422; `lng = -181` → 422; ids repetidos → 422; `lat = NaN` → 422.
    - `GET /health` → 200 sin token.
- [ ] **Step 3:** `pytest` → falla por módulos inexistentes.
- [ ] **Step 4: Implementar** `schemas.py` (restricciones con `Field`: lat −90..90, lng −180..180, `allow_inf_nan=False`, `stops` de 1 a 100, validador de ids únicos), `engine.py` (cargar `engine.wasm` relativo al archivo; si el módulo declara imports WASI, enlazarlos con `Linker.define_wasi()`; llamar `_initialize` si existe; escribir coords en la memoria con `struct.pack_into` en el puntero de `rl_coords`, leer el orden desde `rl_order`), `auth.py`, `main.py` (CORS desde la variable de entorno; título y descripción en español para `/docs`).
- [ ] **Step 5:** `pytest` → todo pasa.
- [ ] **Step 6:** Arrancar con `uvicorn app.main:app --port 8001`, abrir `/docs` y confirmar que el esquema muestra los modelos y los ejemplos.
- [ ] **Step 7:** Commit.

### Task 4: Backend — proyecto, modelos, autenticación y demo

**Files:**
- Create: `backend/pyproject.toml`, `backend/manage.py`, `backend/.env.example`, `backend/config/{__init__,settings,urls,wsgi}.py`, `backend/core/{__init__,apps,models,admin,demo}.py`, `backend/core/migrations/`, `backend/core/management/commands/seed_demo.py`, `backend/core/{views,urls,serializers}.py` (parte de auth), `backend/tests/{conftest,test_auth}.py`, `backend/pytest.ini`

**Interfaces:**
- Produces, modelos (`core/models.py`):
  - `Business(owner: OneToOne User, name: str, depot_lat: float, depot_lng: float)`
  - `Driver(business: FK, name: str, phone: str)`
  - `Order(business: FK, customer_name: str, address: str, lat: float, lng: float, notes: str blank, status: "pending"|"assigned"|"delivered" default "pending", created_at)`
  - `Route(business: FK, driver: FK PROTECT, date: date, status: "planned"|"in_progress"|"done" default "planned", total_km: float, naive_km: float, created_at)`
  - `RouteStop(route: FK related_name="stops", order: OneToOne Order, sequence: int, delivered_at: datetime null)`; orden por defecto `sequence`.
- Produces, `core/demo.py`: `DEMO_USERNAME = "demo"`; `ensure_demo() -> User` (crea usuario, negocio y datos si faltan; idempotente); `reset_demo() -> None` (borra rutas, pedidos y repartidores del negocio demo y los vuelve a crear, en una transacción).
- Datos demo: negocio "Panadería La Espiga", depósito en Cali (`3.4516, -76.5320`), 3 repartidores, 12 pedidos pendientes con coordenadas reales de barrios de Cali (San Antonio, Granada, El Peñón, Ciudad Jardín, San Fernando, Tequendama, Versalles, El Ingenio, Santa Mónica, Alameda, Centenario, Pance).
- Produces, HTTP:
  - `POST /api/auth/token/` y `POST /api/auth/token/refresh/` (simplejwt).
  - `POST /api/auth/demo/` sin autenticación → `{"access": str, "refresh": str}` del usuario demo; llama a `ensure_demo()`.
  - `GET /api/business/me/` → `{"id", "name", "depot_lat", "depot_lng", "is_demo": bool}`.
- Settings: `SIMPLE_JWT = {"ALGORITHM": "HS256", "SIGNING_KEY": env JWT_SIGNING_KEY, "ACCESS_TOKEN_LIFETIME": 12 h, "REFRESH_TOKEN_LIFETIME": 7 d}`; DRF con `JWTAuthentication` e `IsAuthenticated` por defecto; base de datos desde `DATABASE_URL` con caída a SQLite (patrón de la documentación de Vercel); `WSGI_APPLICATION = "config.wsgi.application"`; `STATIC_ROOT = BASE_DIR / "staticfiles"`; WhiteNoise en middleware; `django-cors-headers` con `CORS_ALLOWED_ORIGINS` desde entorno; `ALLOWED_HOSTS` desde entorno más `.vercel.app`; `DEBUG` desde entorno, por defecto `False`; `manage.py` carga `.env.local` y `.env` con `python-dotenv`.
- `pyproject.toml`: `Django>=5.2,<5.3`, `djangorestframework`, `djangorestframework-simplejwt`, `django-cors-headers`, `psycopg[binary]`, `whitenoise`, `httpx`, `python-dotenv`; dev `pytest`, `pytest-django`.

- [ ] **Step 1:** venv en `backend/.venv`, instalar, `django-admin startproject config .` y app `core`. Ajustar settings según el bloque anterior.
- [ ] **Step 2: Tests que fallan** (`test_auth.py`):
  - `POST /api/auth/demo/` → 200 con `access` y `refresh`; crea 12 pedidos y 3 repartidores.
  - Llamarlo dos veces no duplica datos (siguen 12 y 3).
  - `GET /api/business/me/` sin token → 401; con token demo → 200, `is_demo == true`, depósito en Cali.
  - El token `access` decodificado con `JWT_SIGNING_KEY` tiene `token_type == "access"` (contrato con el optimizador).
  - `reset_demo()` tras borrar 5 pedidos deja otra vez 12 pendientes.
- [ ] **Step 3:** `pytest` → falla.
- [ ] **Step 4: Implementar** modelos, migración, `demo.py`, comando `seed_demo` (llama `ensure_demo()`), vistas y urls de auth y `business/me`, registro de los cinco modelos en el admin con `list_display` y filtros útiles.
- [ ] **Step 5:** `pytest` → pasa. `python manage.py migrate && python manage.py seed_demo && python manage.py check --deploy` sin errores bloqueantes.
- [ ] **Step 6:** Commit.

### Task 5: Backend — pedidos y repartidores

**Files:**
- Modify: `backend/core/serializers.py`, `views.py`, `urls.py`
- Create: `backend/core/permissions.py`, `backend/tests/test_orders.py`

**Interfaces:**
- Produces: mixin `BusinessScopedMixin` (en `views.py`) que filtra `get_queryset()` por `request.user.business` y asigna el negocio en `perform_create`. Lo reutiliza la Tarea 6.
- Produces, HTTP (todas con JWT):
  - `GET /api/orders/?status=pending|assigned|delivered`, `POST /api/orders/`, `GET|PATCH|DELETE /api/orders/{id}/`.
    Campos: `id, customer_name, address, lat, lng, notes, status (solo lectura), created_at (solo lectura)`.
  - `GET|POST /api/drivers/`, `GET|PATCH|DELETE /api/drivers/{id}/`. Campos: `id, name, phone`.
- Reglas: lat −90..90 y lng −180..180 (400 si no); borrar o editar coordenadas de un pedido que no está `pending` → 409; más de 200 pedidos en el negocio → 400 con mensaje "Límite de 200 pedidos alcanzado. Restablece el demo."; borrar un repartidor con rutas → 409. Sin paginación. Orden: más recientes primero.

- [ ] **Step 1: Tests que fallan** (`test_orders.py`, fixtures `client_a` y `client_b` de dos negocios distintos en `conftest.py`):
  - Crear pedido → 201, `status == "pending"`, queda en el negocio del usuario aunque el cuerpo envíe otro `business`.
  - A no ve en la lista los pedidos de B; `GET`, `PATCH` y `DELETE` de un pedido de B → 404.
  - `lat = 95` → 400; `lng = 200` → 400.
  - Filtro `?status=pending` devuelve solo pendientes.
  - Pedido `assigned`: `DELETE` → 409.
  - Con 200 pedidos existentes, crear otro → 400.
  - Repartidores: CRUD básico y aislamiento entre negocios.
- [ ] **Step 2:** `pytest tests/test_orders.py` → falla.
- [ ] **Step 3: Implementar** serializers, viewsets con el mixin y router.
- [ ] **Step 4:** `pytest` → pasa todo (incluida Tarea 4).
- [ ] **Step 5:** Commit.

### Task 6: Backend — rutas, optimizador y restablecer demo

**Files:**
- Create: `backend/core/optimizer_client.py`, `backend/tests/test_routes.py`
- Modify: `backend/core/serializers.py`, `views.py`, `urls.py`

**Interfaces:**
- Consumes: contrato `POST /optimize` (Tarea 3); `BusinessScopedMixin` (Tarea 5); `reset_demo()` (Tarea 4).
- Produces, `core/optimizer_client.py`:
  - `@dataclass OptimizerResult(order: list[int], optimized_km: float, naive_km: float)`
  - `class OptimizerUnavailable(Exception)`
  - `optimize_route(depot: tuple[float, float], stops: list[dict], token: str) -> OptimizerResult`; `stops` son `{"id", "lat", "lng"}`; usa `httpx` contra `settings.OPTIMIZER_URL + "/optimize"` con timeout de 10 s y reenvía el token del usuario; cualquier error de red, timeout o respuesta distinta de 200 lanza `OptimizerUnavailable`. También la lanza si `order` no es una permutación exacta de los ids enviados.
- Produces, HTTP:
  - `POST /api/routes/` cuerpo `{"driver": int, "order_ids": [int], "date": "YYYY-MM-DD" (opcional, por defecto hoy)}` → 201 con el detalle.
  - `GET /api/routes/` (lista sin paradas, más recientes primero), `GET /api/routes/{id}/`.
  - Detalle: `{"id", "date", "status", "total_km", "naive_km", "saved_km", "driver": {"id","name"}, "depot": {"lat","lng"}, "stops": [{"id", "sequence", "delivered_at", "order": {"id","customer_name","address","lat","lng"}}]}`.
  - `POST /api/routes/{id}/stops/{stop_id}/deliver/` → 200 con el detalle.
  - `POST /api/demo/reset/` → 204; solo el usuario demo (403 para otros).
- Reglas: `order_ids` de 1 a 100 elementos, sin repetidos, todos del negocio y `pending`; `driver` del negocio. Si falla algo → 400 y nada guardado. Creación dentro de `transaction.atomic()` con `select_for_update()` sobre los pedidos. `OptimizerUnavailable` → 502 `{"detail": "El servicio de optimización no está disponible. Intenta de nuevo en unos segundos."}`. Entregar: fija `delivered_at` si estaba vacío, pedido → `delivered`, ruta → `in_progress`, y `done` cuando todas las paradas están entregadas; repetir la llamada no cambia nada y responde 200.

- [ ] **Step 1: Tests que fallan** (`test_routes.py`; `optimize_route` simulado con `monkeypatch` salvo donde se indique):
  - Crear ruta con 3 pedidos y optimizador simulado que devuelve orden invertido → 201; paradas con `sequence` 1..3 en ese orden; pedidos `assigned`; `total_km`, `naive_km` y `saved_km` guardados.
  - `order_ids` vacío → 400; con repetidos → 400; con un id de otro negocio → 400; con un pedido ya `assigned` → 400; `driver` de otro negocio → 400. En todos: 0 rutas creadas y pedidos intactos.
  - Crear dos veces la misma ruta: la segunda → 400, sigue habiendo 1 ruta.
  - Optimizador simulado lanza `OptimizerUnavailable` → 502 con el mensaje exacto; 0 rutas; pedidos siguen `pending`.
  - `optimize_route` real con `httpx.MockTransport`: respuesta 500 → `OptimizerUnavailable`; timeout → `OptimizerUnavailable`; `order` con un id ajeno → `OptimizerUnavailable`; verifica que envía `Authorization: Bearer <token>`.
  - Entregar primera parada → ruta `in_progress`, pedido `delivered`; entregar la misma otra vez → 200 y `delivered_at` no cambia; entregar todas → ruta `done`.
  - Entregar una parada de la ruta de otro negocio → 404.
  - `POST /api/demo/reset/` como demo → 204 y quedan 12 pedidos pendientes y 0 rutas; como otro usuario → 403.
- [ ] **Step 2:** `pytest tests/test_routes.py` → falla.
- [ ] **Step 3: Implementar** cliente, serializers de entrada y detalle, vistas y urls.
- [ ] **Step 4:** `pytest` → pasa todo el backend.
- [ ] **Step 5: Integración local real.** Con el optimizador en `:8001` y el backend en `:8000` (misma `JWT_SIGNING_KEY` en ambos `.env`): pedir token demo, crear una ruta con 6 pedidos con `curl`, confirmar 201 y `total_km <= naive_km`.
- [ ] **Step 6:** Commit.

### Task 7: Frontend — base, sesión y pedidos

**Files:**
- Create: `frontend/index.html`, `css/app.css`, `vendor/*`, `js/config.js`, `js/app.js`, `js/services/{auth,api,map}.service.js`, `js/controllers/{login,orders}.controller.js`, `views/{login,orders}.html`

**Interfaces:**
- Consumes: API del backend (Tareas 4 y 5).
- Produces:
  - `js/config.js`: `window.RL_CONFIG = { API_URL, OPTIMIZER_DOCS_URL, REPO_URL }`; elige URLs locales (`http://localhost:8000/api`, `http://localhost:8001/docs`) si el host es `localhost` o `127.0.0.1`, y de producción en otro caso (se completan en Tarea 10).
  - Módulo Angular `rutalibre` con rutas `#!/login`, `#!/pedidos`, `#!/planificar`, `#!/rutas`, `#!/rutas/:id`; por defecto `#!/pedidos`.
  - `AuthService`: `login(username, password)`, `loginDemo()`, `logout()`, `isAuthenticated()`, `getToken()`; guarda en `localStorage` bajo la clave `rutalibre.auth`.
  - `ApiService`: `get(path, params)`, `post(path, body)`, `patch(path, body)`, `delete(path)`; devuelve promesas con `response.data`.
  - Interceptor `authInterceptor`: añade `Authorization: Bearer`; ante 401 hace `logout()` y redirige a `#!/login`.
  - `MapService`: `create(elementId, center)`, `setMarkers(map, points)`, `drawRoute(map, points, {color, dashed})`, `clear(map)`, `onClick(map, cb)`.
- Librerías dentro del repo en `vendor/`: `angular.min.js` y `angular-route.min.js` 1.8.3, `leaflet.js`, `leaflet.css` y sus imágenes 1.9.4. Sin CDN.

- [ ] **Step 1:** Descargar las librerías con `npm pack` (o desde cdnjs) a `vendor/` y verificar versiones en las cabeceras de los archivos.
- [ ] **Step 2:** Antes de escribir estilos, usar el skill `frontend-design` para fijar la dirección visual. Requisitos: interfaz en español, usable en móvil (el mapa pasa debajo de la lista en pantallas angostas), barra superior con navegación, nombre del negocio, botón "Restablecer demo" (solo si `is_demo`) y "Salir"; pie "Cómo está hecho" con enlaces a `REPO_URL` y `OPTIMIZER_DOCS_URL` y la frase "Las rutas se calculan con un motor en C++ compilado a WebAssembly".
- [ ] **Step 3: Implementar** shell, servicios, interceptor y guard de sesión (`$routeChangeStart` redirige a login si no hay sesión).
- [ ] **Step 4: Login**: formulario usuario/contraseña y botón principal "Entrar al demo". Errores visibles ("Usuario o contraseña incorrectos", "No se pudo conectar con el servidor").
- [ ] **Step 5: Pedidos**: lista con estado, formulario de alta (cliente, dirección, notas) cuya ubicación se fija con un clic en el mapa (centrado en el depósito), borrar pedidos pendientes, mensajes de error del backend mostrados tal cual (`detail` o errores por campo). No se puede guardar sin ubicación.
- [ ] **Step 6: Verificación en navegador** (servir con `python -m http.server 5500` desde `frontend/`, backend en `:8000` con CORS para `http://localhost:5500`):
  - "Entrar al demo" lleva a pedidos y lista 12.
  - Crear y borrar un pedido funciona y el mapa muestra los marcadores.
  - Poner un token inválido a mano en `localStorage` y recargar → vuelve al login, sin errores en consola.
  - Ancho de 375 px: sin scroll horizontal.
- [ ] **Step 7:** Commit.

### Task 8: Frontend — motor en el navegador, planificador y rutas

**Files:**
- Create: `frontend/js/engine-loader.js`, `js/services/engine.service.js`, `js/controllers/{planner,routes,route-detail}.controller.js`, `views/{planner,routes,route-detail}.html`, `frontend/tests/engine-loader.test.mjs`
- Modify: `frontend/index.html` (scripts), `js/app.js` (rutas)

**Interfaces:**
- Consumes: `frontend/wasm/engine.wasm` (Tarea 2); API de rutas (Tarea 6); `MapService` (Tarea 7).
- Produces:
  - `js/engine-loader.js`: función global `RLEngine.instantiate(bytes: ArrayBuffer) -> Promise<{ optimize(depot: {lat,lng}, stops: [{lat,lng}]) -> {order: number[], optimizedKm: number, naiveKm: number} }>`. Construye el objeto de imports recorriendo `WebAssembly.Module.imports` y asignando funciones vacías; llama `_initialize` si existe; escribe en `rl_coords` con `Float64Array` y lee `rl_order` con `Int32Array`. Lanza `RangeError` si hay más de 100 paradas. También exporta para Node (`module.exports` si existe).
  - `EngineService`: `ready() -> Promise`, `optimize(depot, stops)`; descarga `wasm/engine.wasm` una sola vez. Si el navegador no soporta WebAssembly o falla la carga, `ready()` se rechaza.

- [ ] **Step 1: Test que falla** (`node --test frontend/tests/`): carga `frontend/wasm/engine.wasm` con `RLEngine.instantiate`; cuadrado cruzado → `optimizedKm < naiveKm`; `order` es permutación; 0 paradas → `order` vacío y 0 km; 101 paradas → `RangeError`; el resultado de 10 puntos fijos coincide con el que da el optimizador Python para los mismos puntos (valores esperados escritos en el test tras calcularlos una vez con `optimizer/app/engine.py`).
- [ ] **Step 2:** Ejecutar → falla. Implementar `engine-loader.js`. Ejecutar → pasa.
- [ ] **Step 3: Planificador** (`#!/planificar`): lista de pedidos pendientes con casillas y "Seleccionar todos", selector de repartidor. Con 2 o más seleccionados, el mapa dibuja la ruta ingenua (línea gris punteada) y la optimizada (línea de color), y un panel muestra "Sin optimizar: X km", "Optimizada: Y km", "Ahorro: Z km (P %)". Se recalcula al instante en cada cambio, con `EngineService`. Botón "Confirmar ruta" → `POST /routes/` → navega al detalle. Mientras espera: botón deshabilitado y texto "Calculando en el servidor…". Ante 502 o 400: muestra `detail` y vuelve a habilitar el botón. Si `EngineService.ready()` falla: aviso "Tu navegador no pudo cargar la vista previa; la ruta se calculará en el servidor" y el botón sigue funcionando. Más de 100 seleccionados: botón deshabilitado con aviso.
- [ ] **Step 4: Rutas** (`#!/rutas`): tabla con fecha, repartidor, estado, km y ahorro. Estado vacío con enlace a planificar.
- [ ] **Step 5: Detalle** (`#!/rutas/:id`): mapa con el circuito numerado, lista de paradas en orden, botón "Marcar entregado" por parada (deshabilitado mientras responde; las entregadas muestran la hora), progreso "n de m entregadas".
- [ ] **Step 6: "Restablecer demo"** en la barra: confirma con un diálogo propio (no `confirm()` del navegador), llama `POST /demo/reset/` y recarga la vista actual.
- [ ] **Step 7: Verificación en navegador** con backend y optimizador locales:
  - Seleccionar los 12 pedidos: la comparación aparece sin esperar y el ahorro es positivo.
  - Confirmar: se crea la ruta y `total_km` del detalle coincide con el "Optimizada" de la vista previa (misma cifra con 1 decimal).
  - Apagar el optimizador y confirmar otra ruta: aparece el mensaje del 502 y el botón se rehabilita.
  - Marcar todas las paradas: la ruta pasa a "Completada".
  - Restablecer demo: vuelven 12 pedidos pendientes.
  - Sin errores en la consola durante todo el recorrido.
- [ ] **Step 8:** Commit.

### Task 9: Integración continua

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: comandos de test de las Tareas 2, 3, 6 y 8.

- [ ] **Step 1:** Workflow en `push` y `pull_request` con cuatro jobs en `ubuntu-latest`:
  - `engine`: `cmake -S engine -B build && cmake --build build && ctest --test-dir build --output-on-failure`; luego instalar emsdk en la versión anotada en la Tarea 1, `python engine/build.py --test` y `python engine/build.py`.
  - `optimizer`: Python 3.12, instalar, `pytest`. Depende de `engine` y usa el `engine.wasm` recién compilado como artefacto, para probar que el fuente actual pasa los mismos tests que el binario versionado.
  - `backend`: Python 3.12, instalar, `pytest` (SQLite).
  - `frontend`: Node 24, `node --test frontend/tests/`.
- [ ] **Step 2:** Push y comprobar con `gh run watch` que los cuatro jobs terminan en verde. Corregir lo que falle.
- [ ] **Step 3:** Commit (si hubo correcciones).

### Task 10: Despliegue

**Files:**
- Modify: `frontend/js/config.js` (URLs de producción), `backend/.env.example`, `optimizer/.env.example`
- Create si hace falta: `backend/vercel.json`, `optimizer/vercel.json` (solo `maxDuration`)

**Interfaces:**
- Produces: tres URLs públicas (frontend, API, optimizador) y la base de datos en Neon con migraciones y datos demo.

Pasos que requieren a Esteban: crear cuenta y proyecto en Neon y pegar la cadena de conexión; `npx vercel login`; si se quiere despliegue automático por push, autorizar la app de GitHub de Vercel.

- [ ] **Step 1:** Generar `DJANGO_SECRET_KEY` y `JWT_SIGNING_KEY` con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. No se guardan en el repo.
- [ ] **Step 2: Optimizador.** En `optimizer/`: `npx vercel link` (proyecto `rutalibre-optimizer`), `vercel env add` para `JWT_SIGNING_KEY` y `CORS_ALLOWED_ORIGINS`, `npx vercel deploy --prod`. Verificar `GET <url>/health` → `{"status":"ok","engine":"wasm"}`; esto confirma que `engine.wasm` viajó en el bundle. Si no viajó, declararlo como archivo incluido en la configuración del proyecto y redesplegar.
- [ ] **Step 3: Base de datos.** Con `DATABASE_URL` de Neon en `backend/.env.local`: `python manage.py migrate`, `python manage.py seed_demo`, `python manage.py createsuperuser` (credenciales las define Esteban).
- [ ] **Step 4: Backend.** En `backend/`: `npx vercel link` (proyecto `rutalibre-api`), variables `DATABASE_URL`, `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY` (la misma), `OPTIMIZER_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`; `npx vercel deploy --prod`. Verificar: `POST <url>/api/auth/demo/` → 200; `<url>/admin/` carga con estilos.
- [ ] **Step 5: Frontend.** Escribir las URLs de producción en `js/config.js`, commit. En `frontend/`: `npx vercel link` (proyecto `rutalibre`, framework "Other", sin build), `npx vercel deploy --prod`. Actualizar `CORS_ALLOWED_ORIGINS` de backend y optimizador con la URL final del frontend y redesplegar ambos.
- [ ] **Step 6: Prueba de humo en producción**, en una ventana privada del navegador: entrar al demo, ver 12 pedidos, planificar con todos, confirmar ruta, marcar dos entregas, restablecer demo, abrir `/docs` del optimizador. Sin errores de CORS en consola. Repetir la creación de ruta tras 10 minutos de inactividad para medir el arranque en frío; si supera el timeout de 10 s, subir el timeout del cliente y `maxDuration` y anotarlo en un ADR.
- [ ] **Step 7:** Conectar los tres proyectos al repo de GitHub con su "Root Directory" (`backend`, `optimizer`, `frontend`) para desplegar en cada push. Si la autorización no está lista hoy, queda el despliegue por CLI y se anota como pendiente en el README.
- [ ] **Step 8:** Commit y push.

### Task 11: Documentación

**Files:**
- Modify: `README.md`
- Create: `docs/architecture.md`, `docs/adr/0001-motor-cpp-en-webassembly.md`, `docs/adr/0002-vercel-y-neon-en-lugar-de-aws.md`, `docs/adr/0003-jwt-compartido-entre-servicios.md`, `docs/EXPLICACION.md`

- [ ] **Step 1: README** en español con: descripción en dos frases; enlace al demo y botón "Entrar al demo" explicado; captura de la vista del planificador (tomada del sitio en producción); diagrama de arquitectura en Mermaid; tabla "Requisito de la convocatoria → dónde está" con enlaces a archivos (Django/DRF, AngularJS, FastAPI, C++, AWS, pruebas, documentación); cómo correr en local (tres terminales, sin Docker); cómo recompilar el motor; sección "Camino a AWS" (texto del apartado 7 del diseño, sin afirmar nada que no exista); hoja de ruta con las fases A–F; insignia del CI.
- [ ] **Step 2: ADRs**, media página cada uno: contexto, decisión, consecuencias, alternativas descartadas.
- [ ] **Step 3: `docs/EXPLICACION.md`**: recorrido para estudiar el código en este orden: motor (algoritmos con un ejemplo a mano de 2-opt), cómo viaja la memoria entre Python/JS y el wasm, optimizador, modelos y vistas de Django, flujo completo de "crear ruta" con los archivos y funciones que intervienen, estructura de AngularJS, despliegue. Incluye preguntas de autoevaluación por sección.
- [ ] **Step 4:** Revisar cada afirmación del README contra el demo en producción. Lo que no esté construido se mueve a la hoja de ruta.
- [ ] **Step 5:** Commit y push. Confirmar CI en verde.

---

## Fases posteriores

Cada una tendrá su propio diseño corto y plan. Orden por valor para la convocatoria:

| Fase | Entrega | Cubre |
|------|---------|-------|
| A | Foto de evidencia al entregar: `boto3`, URL prefirmada, almacenamiento compatible con S3 gratuito y sin pausa (verificar Backblaze B2 antes de elegir) | S3 con código real |
| B | `infra/aws/` en Terraform: EC2, RDS, S3, IAM de mínimo privilegio; `terraform validate` en CI, sin aplicar | EC2, RDS, IAM |
| C | Microservicio Flask de notificaciones (webhook al completar ruta) | Flask (opcional) |
| D | Vista del repartidor, registro de usuarios, edición del depósito | Producto |
| E | LocalStack: S3 e IAM en local con políticas versionadas | IAM |
| F | Distancias por carretera con un servicio de enrutamiento abierto | Realismo |

Si sobra tiempo hoy, se empieza por la Fase A y luego la B.
