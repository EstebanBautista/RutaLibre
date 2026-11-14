# Fase A — Fotos de evidencia en S3: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adjuntar una foto de evidencia a cada parada, guardada en Backblaze B2 con `boto3` y URLs prefirmadas.

**Architecture:** Un módulo `core/storage.py` envuelve `boto3` (cliente S3 apuntando a B2). Django firma una URL PUT, el navegador sube la foto reducida directo al bucket, y Django confirma con `HEAD` antes de guardar la clave en `RouteStop`. El detalle de la ruta entrega URLs GET prefirmadas.

**Tech Stack:** boto3, moto (tests), Django/DRF existentes, AngularJS existente, Backblaze B2.

**Spec:** `docs/superpowers/specs/2026-11-14-fase-a-fotos-s3-design.md`

## Global Constraints

- Bucket `rutalibre-evidencias`, endpoint `https://s3.us-east-005.backblazeb2.com`, región `us-east-005`.
- Variables: `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`. Si falta alguna, fotos desactivadas.
- `MAX_PHOTO_BYTES = 2 * 1024 * 1024`; `UPLOAD_URL_TTL = 300`; `VIEW_URL_TTL = 3600`; solo `image/jpeg`.
- Clave: `businesses/{business_id}/routes/{route_id}/stops/{stop_id}/{uuid4hex}.jpg`.
- Imagen reducida en el navegador: lado mayor ≤ 1600 px, JPEG calidad 0,8.
- Las claves de B2 nunca se imprimen, ni se escriben en el repo o en el chat.
- La entrega (`deliver`) nunca depende del almacenamiento.
- Código en inglés; interfaz y mensajes en español.

## Review Focus

1. **Bucket caído durante "Restablecer demo"**: el reset termina igual (datos restaurados) y solo se registra el fallo. Test en Tarea 2.
2. **Confirmar dos veces la misma clave** (doble clic): la segunda confirmación responde 200 y no borra la foto vigente. Test en Tarea 2.
3. **Confirmar sin haber subido** (la subida falló y el cliente confirma igual): 400 "No se encontró la foto subida. Vuelve a intentarlo." y la parada no cambia. Test en Tarea 2.
4. **Foto que no es imagen o archivo enorme elegido en el navegador**: el frontend rechaza tipos que no sean imagen antes de subir, y el servidor sigue validando tamaño y tipo. Verificación manual en Tarea 3.
5. **URL de lectura vencida** (página abierta más de 1 h): la miniatura rota no rompe la vista; recargar el detalle trae URLs nuevas. Verificación manual en Tarea 3.

## Archivos

```
backend/core/storage.py              boto3: configuración, firma, head, borrado
backend/core/photos.py               Reglas de la foto de una parada (pedir URL, confirmar)
backend/core/models.py               RouteStop.photo_key, photo_uploaded_at
backend/core/migrations/0002_*.py
backend/core/views.py, serializers.py, urls.py, demo.py, exceptions.py
backend/tests/test_storage.py, test_photos.py
frontend/js/photo-utils.js           fitWithin (puro, testeable en Node)
frontend/js/services/photo.service.js
frontend/js/controllers/route-detail.controller.js, views/route-detail.html, css/app.css
frontend/tests/photo-utils.test.mjs
README.md, docs/architecture.md, docs/EXPLICACION.md, docs/adr/0004-fotos-con-url-prefirmada.md
```

---

### Task 1: Módulo de almacenamiento

**Files:** Create `backend/core/storage.py`, `backend/tests/test_storage.py`. Modify `backend/config/settings.py`, `backend/requirements.txt` (+`boto3>=1.35`), `backend/pyproject.toml` (+`boto3`, dev `moto[s3]>=5`), `backend/.env.example`, `.github/workflows/ci.yml` (instalar `moto[s3]`).

**Interfaces — Produces (`core/storage.py`):**
```python
class StorageError(Exception): ...          # any boto3/botocore failure
@dataclass(frozen=True)
class ObjectInfo: size: int; content_type: str
def is_configured() -> bool
def presigned_put(key: str, content_type: str = "image/jpeg", expires: int = UPLOAD_URL_TTL) -> str
def presigned_get(key: str, expires: int = VIEW_URL_TTL) -> str
def head(key: str) -> ObjectInfo | None        # None when the object does not exist (404)
def delete(key: str) -> None                   # idempotent
def delete_prefix(prefix: str) -> int          # returns number of objects deleted
```
Settings: `S3 = {"endpoint_url", "region", "bucket", "access_key_id", "secret_access_key"}` leídos del entorno; vacíos por defecto.

- [ ] **Step 1: Tests que fallan** (`test_storage.py`, `@mock_aws`, fixture que fija `settings.S3` con endpoint `None` para moto y crea el bucket):
  - `is_configured()` es `False` con cualquier valor vacío y `True` con todos.
  - `presigned_put("a/b.jpg")` devuelve una URL que contiene `a/b.jpg`, `X-Amz-Expires=300` y `X-Amz-Signature`.
  - `presigned_get(...)` contiene `X-Amz-Expires=3600`.
  - `head` de una clave inexistente → `None`; tras `put_object` de 10 bytes `image/jpeg` → `ObjectInfo(10, "image/jpeg")`.
  - `delete` de clave inexistente no lanza.
  - `delete_prefix("businesses/1/")` borra 3 objetos bajo el prefijo, devuelve 3 y no toca `businesses/2/x.jpg`.
  - Con bucket inexistente, `head` lanza `StorageError` (no `ClientError`).
- [ ] **Step 2:** `pytest tests/test_storage.py` → falla (módulo no existe).
- [ ] **Step 3: Implementar.** Cliente `boto3.client("s3", ...)` creado bajo demanda y cacheado por tupla de configuración, con `Config(signature_version="s3v4", s3={"addressing_style": "path"}, request_checksum_calculation="when_required", response_checksum_validation="when_required", retries={"max_attempts": 2}, connect_timeout=5, read_timeout=10)`. Las opciones de checksum evitan cabeceras CRC32 que B2 no acepta en URLs prefirmadas. `head` traduce el 404 a `None` y todo otro `ClientError`/`BotoCoreError` a `StorageError`. `delete_prefix` usa `list_objects_v2` paginado + `delete_objects` en lotes de 1000.
- [ ] **Step 4:** `pytest` (todo el backend) → pasa.
- [ ] **Step 5:** Commit.

### Task 2: Foto de una parada en la API

**Files:** Create `backend/core/photos.py`, `backend/tests/test_photos.py`, migración `0002`. Modify `models.py`, `serializers.py`, `views.py`, `urls.py` (nada: acciones del viewset), `demo.py`, `exceptions.py`.

**Interfaces:**
- Consumes: todo `core.storage` (Tarea 1).
- Produces:
  - `RouteStop.photo_key: CharField(max_length=200, blank=True, default="")`, `RouteStop.photo_uploaded_at: DateTimeField(null=True, blank=True)`.
  - `core/photos.py`: `key_prefix(stop) -> str` (`businesses/{b}/routes/{r}/stops/{s}/`), `new_key(stop) -> str`, `request_upload(stop) -> dict` → `{"upload_url": str, "key": str, "headers": {"Content-Type": "image/jpeg"}}`, `confirm_upload(stop, key: str) -> None` (lanza `BadRequest` con los mensajes de abajo), `view_url(stop) -> str | None`.
  - HTTP `POST /api/routes/{id}/stops/{stop_id}/photo/upload-url/` → 200 con el dict anterior.
  - HTTP `POST /api/routes/{id}/stops/{stop_id}/photo/` cuerpo `{"key": str}` → 200 con el detalle de la ruta.
  - Detalle de ruta: cada parada suma `photo_url: str | null` y `photo_uploaded_at`.
  - `GET /api/business/me/` suma `photos_enabled: bool`.
  - `exceptions.PhotosDisabled` (503): "Las fotos de evidencia no están configuradas en este servidor."
  - `exceptions.StorageDown` (502): "El almacenamiento de fotos no responde. La entrega no se ve afectada; intenta de nuevo."
- Mensajes 400 exactos: prefijo ajeno → "La foto no corresponde a esta parada."; sin objeto → "No se encontró la foto subida. Vuelve a intentarlo."; > 2 MB → "La foto supera 2 MB."; tipo distinto → "La foto debe ser JPEG.". En los dos últimos se borra el objeto.

- [ ] **Step 1: Tests que fallan** (`test_photos.py`, `@mock_aws`, bucket creado, ruta con 2 paradas del negocio A; la subida se simula con `put_object` sobre la clave devuelta):
  - Pedir URL → 200, `key` empieza por `businesses/{a}/routes/{r}/stops/{s}/` y termina en `.jpg`, `headers == {"Content-Type": "image/jpeg"}`.
  - Subir + confirmar → 200; la parada tiene `photo_url` no nulo y `photo_uploaded_at`.
  - Confirmar sin subir → 400 con el mensaje exacto; parada sin foto.
  - Confirmar con una clave del prefijo de la otra parada → 400 "La foto no corresponde a esta parada.".
  - Objeto de 2 MB + 1 byte → 400 "La foto supera 2 MB." y el objeto ya no existe.
  - Objeto `image/png` → 400 "La foto debe ser JPEG." y el objeto ya no existe.
  - Reemplazar: confirmar foto 1, luego foto 2 → la clave 1 ya no existe; la 2 sí.
  - Confirmar dos veces la misma clave → ambas 200; el objeto sigue existiendo.
  - Negocio B pide URL o confirma sobre la parada de A → 404.
  - Sin configuración (`settings.S3` vacío): pedir URL → 503 con el mensaje exacto; `business/me` → `photos_enabled == false`; el detalle de ruta trae `photo_url: null`; `deliver` sigue respondiendo 200.
  - `storage.presigned_put` que lanza `StorageError` (monkeypatch) → 502 con el mensaje exacto.
  - `reset_demo()` con 2 fotos del demo en el bucket y una de otro negocio → quedan 0 del demo, 1 ajena.
  - `reset_demo()` con `delete_prefix` lanzando `StorageError` → no lanza; los datos demo quedan restaurados.
- [ ] **Step 2:** `pytest tests/test_photos.py` → falla.
- [ ] **Step 3: Implementar.** Modelo + `makemigrations core`. Acciones en `RouteViewSet` con `url_path=r"stops/(?P<stop_id>\d+)/photo/upload-url"` y `r"stops/(?P<stop_id>\d+)/photo"`; la parada se busca con `route=self.get_object()` (404 entre negocios). `confirm_upload` corre en `transaction.atomic()` con `select_for_update` sobre la parada; borra la clave anterior **después** de guardar la nueva y solo si es distinta. `view_url` devuelve `None` si no hay clave o fotos desactivadas, y también ante `StorageError` (la vista no se cae). `reset_demo` llama `delete_prefix(f"businesses/{id}/")` solo si `is_configured()`, dentro de `try/except StorageError` con `logger.warning`.
- [ ] **Step 4:** `pytest` → todo el backend pasa (65 previos + nuevos).
- [ ] **Step 5:** Commit.

### Task 3: Frontend — adjuntar y ver la foto

**Files:** Create `frontend/js/photo-utils.js`, `frontend/js/services/photo.service.js`, `frontend/tests/photo-utils.test.mjs`. Modify `frontend/index.html` (scripts), `js/controllers/route-detail.controller.js`, `js/controllers/shell.controller.js` (nada si `photos_enabled` se lee del negocio), `views/route-detail.html`, `css/app.css`.

**Interfaces:**
- Consumes: endpoints de la Tarea 2.
- Produces:
  - `photo-utils.js`: `RLPhoto.fitWithin(width: number, height: number, max: number) -> {width, height}` (enteros, conserva proporción, nunca agranda). Exporta para Node igual que `engine-loader.js`.
  - `PhotoService.upload(routeId, stopId, file: File) -> Promise<routeDetail>`: valida `file.type` empieza por `image/` (si no, rechaza con `Error('Elige un archivo de imagen.')`), reduce con `canvas.toBlob(..., 'image/jpeg', 0.8)` usando `fitWithin(…, 1600)`, pide URL, hace `PUT` con `$http` (sin `Authorization`: el interceptor solo lo añade a `API_URL`) y confirma.

- [ ] **Step 1: Test que falla** (`node --test`): `fitWithin(4000, 3000, 1600)` → `{1600, 1200}`; `fitWithin(3000, 4000, 1600)` → `{1200, 1600}`; `fitWithin(800, 600, 1600)` → `{800, 600}`; `fitWithin(1601, 1, 1600)` → `{1600, 1}` (alto mínimo 1).
- [ ] **Step 2:** Ejecutar → falla. Implementar `photo-utils.js` → pasa.
- [ ] **Step 3: Vista.** El controlador carga `/business/me/` para `photosEnabled`. Por parada, si `photosEnabled`: input `type="file" accept="image/*" capture="environment"` oculto tras un botón "Adjuntar foto" (o "Cambiar foto" si ya hay); mientras sube, "Subiendo foto…" y botón deshabilitado; error visible por parada con el `detail` del servidor o el `Error` local. Si hay `photo_url`, miniatura de 56×56 px (`object-fit: cover`) que abre la foto en una pestaña nueva; `onerror` la oculta. "Marcar entregado" sigue igual e independiente.
- [ ] **Step 4: Verificación local** (backend con `.env.local` que incluye las claves de B2, optimizador y frontend locales): adjuntar una foto de >3 MB → sube reducida (<500 KB en el bucket); aparece la miniatura; cambiar la foto la reemplaza; elegir un `.txt` muestra "Elige un archivo de imagen."; con las variables S3 vaciadas el botón no aparece y entregar funciona; sin errores en consola.
- [ ] **Step 5:** Commit.

### Task 4: Credenciales, CORS del bucket y despliegue

**Files:** Modify `backend/.env.local` (local, ignorado) y variables de Vercel. Create `.tools/b2_setup.py` (fuera del repo) si hace falta.

Pasos que requieren a Esteban: escribir `S3_ACCESS_KEY_ID` y `S3_SECRET_ACCESS_KEY` en `backend/.env.local` con un editor (Claude abre el archivo con el resto de valores ya escritos y las dos claves vacías).

- [ ] **Step 1:** Añadir a `backend/.env.local` las líneas `S3_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com`, `S3_REGION=us-east-005`, `S3_BUCKET=rutalibre-evidencias`, `S3_ACCESS_KEY_ID=`, `S3_SECRET_ACCESS_KEY=`. Pedir a Esteban que complete las dos últimas.
- [ ] **Step 2:** Verificar sin imprimir secretos: script que carga `.env.local`, ejecuta `presigned_put`, sube 10 bytes con `httpx.put`, `head`, `delete`. Esperado: `ok`.
- [ ] **Step 3: CORS.** Intentar `put_bucket_cors` (orígenes `https://rutalibre-chi.vercel.app`, `http://localhost:5500`; métodos `PUT`, `GET`; cabeceras `content-type`; `MaxAgeSeconds 3600`). Si B2 responde que no lo implementa, pedir a Esteban configurarlo en el panel de B2 (Bucket → CORS Rules) con esos valores, y anotar la decisión en el registro.
- [ ] **Step 4:** Verificar CORS con `curl -X OPTIONS` contra una URL prefirmada con `Origin: https://rutalibre-chi.vercel.app` → `Access-Control-Allow-Origin` presente.
- [ ] **Step 5:** Cargar las 5 variables en el proyecto Vercel `rutalibre-api` leyendo `.env.local` desde Python y `vercel env add` por entrada estándar (sin shell). Push a `main` → despliegue automático.
- [ ] **Step 6: Prueba en producción:** entrar al demo, crear ruta, adjuntar foto, ver miniatura, restablecer demo → el prefijo del demo queda vacío en el bucket.

### Task 5: Documentación

**Files:** Modify `README.md`, `docs/architecture.md`, `docs/EXPLICACION.md`. Create `docs/adr/0004-fotos-con-url-prefirmada.md`.

- [ ] **Step 1:** README: fila AWS de la tabla → "S3 con código real: `boto3`, URLs prefirmadas, bucket privado (Backblaze B2, compatible con S3)" con enlaces a `core/storage.py` y `core/photos.py`; "Camino a AWS": fotos ya en S3-compatible; bloque con la política IAM equivalente (`s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` sobre `arn:aws:s3:::rutalibre-evidencias/*` y `s3:ListBucket` sobre el bucket); Fase A marcada como hecha; conteos de tests actualizados.
- [ ] **Step 2:** `architecture.md`: diagrama de secuencia de la subida (pedir URL → PUT al bucket → confirmar con HEAD).
- [ ] **Step 3:** ADR 0004: por qué URL prefirmada y no subir a Django (límite de Vercel, patrón S3, menor costo), alternativas descartadas.
- [ ] **Step 4:** `EXPLICACION.md`: sección 8 "Fotos y URLs prefirmadas" con preguntas.
- [ ] **Step 5:** Commit y push; CI en verde.
