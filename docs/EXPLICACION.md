# Guía para estudiar el código de RutaLibre

Recorrido en el orden en que conviene leerlo: de lo más pequeño (el algoritmo) a lo más grande (el sistema desplegado). Cada sección dice qué archivos abrir, qué mirar y termina con preguntas para comprobar que lo entendiste.

---

## 1. El motor C++

**Archivos:** `engine/src/route.hpp`, `engine/src/route.cpp`, `engine/tests/test_route.cpp`

### Representación

Las coordenadas viajan en un solo arreglo de `double`:

```
coords = [lat_depósito, lng_depósito, lat_parada0, lng_parada0, lat_parada1, ...]
```

Dentro del motor, el **nodo 0** es el depósito y el **nodo i+1** es la parada i. Un recorrido (`tour`) guarda nodos: `tour[0] = 0`, luego las paradas, y al final otra vez `0`. Así cada tramo es `tour[k] → tour[k+1]`.

### Haversine

Distancia sobre una esfera. Se clampa `h` entre 0 y 1 porque el redondeo puede dejarlo en 1,0000000002, y `asin` de eso da `NaN`.

### Vecino más cercano

Desde el nodo actual, ir a la parada no visitada más cercana. Es O(n²). En los empates gana el índice menor, para que el resultado sea siempre el mismo.

### 2-opt, con un ejemplo a mano

Recorrido con un cruce: `D → A → C → B → D`, donde A–C y B–D se cruzan.

Se prueban pares de tramos. Con los tramos `(D→A)` y `(B→D)`, el algoritmo mira el trozo entre ellos, `A C B`. Si `dist(D,B) + dist(A,D)` es menor que `dist(D,A) + dist(B,D)` no hay ganancia (es el mismo). En cambio, con los tramos `(A→C)` y `(B→D)`:

```
delta = dist(A,B) + dist(C,D) − dist(A,C) − dist(B,D)
```

Si `delta < 0`, conviene unir A con B y C con D. Para eso basta **invertir el trozo entre ellos** (`C B` pasa a `B C`) y queda `D → A → B → C → D`, sin cruce. Se repite hasta una pasada completa sin mejoras. Cada cambio aceptado acorta el circuito en más de `1e-9`, así que el ciclo siempre termina.

### Sin memoria dinámica

`g_dist[101][101]` es estático. Por eso el motor no necesita `malloc` y el `.wasm` no importa nada. El costo: no es reentrante (dos llamadas a la vez se pisarían) y tiene un máximo de 100 paradas.

**Preguntas**
- ¿Por qué `optimize` con 1 parada devuelve el doble de la distancia depósito–parada?
- ¿Qué pasaría si el umbral de mejora fuera `0` en lugar de `1e-9`?
- ¿Por qué el test de "puntos idénticos" comprueba que el resultado no sea `NaN`?

---

## 2. Del C++ al WebAssembly

**Archivos:** `engine/include/rutalibre.h`, `engine/src/wasm_api.cpp`, `engine/build.py`

- `extern "C"` evita el *name mangling* de C++: la función se exporta como `rl_optimize` y no como `_Z11rl_optimizei`.
- `--no-entry` indica que es una librería, sin `main`.
- `-sSTANDALONE_WASM=1` genera un `.wasm` sin JavaScript de soporte de Emscripten.
- `rl_coords()` y `rl_order()` devuelven **direcciones** (enteros) dentro de la memoria lineal del módulo. El anfitrión escribe y lee bytes en esas direcciones.

`build.py --test` compila los tests a WebAssembly y los ejecuta con Node. El CI además los compila de forma nativa con g++ y CMake.

**Preguntas**
- ¿Qué es la "memoria lineal" de un módulo WebAssembly?
- ¿Por qué el resultado de `rl_order()` se lee como `int32` y no como `int64`?

---

## 3. El motor desde Python y desde el navegador

**Archivos:** `optimizer/app/engine.py`, `frontend/js/engine-loader.js`, `frontend/tests/engine-loader.test.mjs`

Ambos hacen lo mismo:

1. Instanciar el módulo y llamar `_initialize` si existe.
2. Escribir las coordenadas en `rl_coords()`. En Python: `struct.pack("<…d")`, *little-endian* porque WebAssembly lo es. En JS: un `Float64Array` sobre `memory.buffer`.
3. Llamar `rl_naive_km(n)` y `rl_optimize(n)`.
4. Leer `n` enteros de `rl_order()`.

En Python hay un `threading.Lock`: un `Store` de wasmtime no se debe usar desde dos hilos, y el motor tiene estado estático. `get_engine()` usa `lru_cache` para compilar el módulo una sola vez por proceso.

El último test del frontend compara el resultado del navegador con valores calculados por la versión de Python: así se garantiza que la vista previa y la ruta guardada coinciden.

**Preguntas**
- ¿Por qué el `Float64Array` se crea dentro de cada llamada y no una sola vez?
- ¿Qué pasaría sin el `Lock` si FastAPI atendiera dos peticiones en paralelo?

---

## 4. El optimizador FastAPI

**Archivos:** `optimizer/app/main.py`, `schemas.py`, `auth.py`, `optimizer/tests/`

- **Validación con Pydantic:** latitud y longitud con rango (`ge`, `le`), `allow_inf_nan=False`, entre 1 y 100 paradas, y un `model_validator` para ids únicos.
- **Manejador de 422 propio:** el de FastAPI copia el valor inválido en la respuesta. Si ese valor es `NaN`, la respuesta no se puede serializar a JSON y el cliente recibiría un 500. Hay un test para eso.
- **`require_user`** es una dependencia (`Depends`): FastAPI la ejecuta antes del endpoint y, si lanza 401, el endpoint no corre.
- El orden que devuelve el motor son **índices**; `main.py` los traduce a los **ids** que mandó el cliente.

**Preguntas**
- ¿Por qué `jwt.decode` recibe `algorithms=["HS256"]` explícito?
- ¿Dónde se genera la documentación de `/docs`?

---

## 5. El backend Django

**Archivos:** `backend/core/models.py`, `views.py`, `serializers.py`, `optimizer_client.py`, `demo.py`, `backend/tests/`

### Modelos

`Business → Driver, Order, Route → RouteStop`. Detalles:
- `RouteStop.order` es `OneToOneField`: un pedido está en una sola ruta.
- `Route.driver` usa `on_delete=PROTECT`: no se puede borrar un repartidor con rutas. La vista convierte el `ProtectedError` en 409.
- `UniqueConstraint(route, sequence)`: no puede haber dos paradas en la misma posición.

### Aislamiento

`BusinessScopedMixin.get_queryset()` filtra por `request.user.business`. Pedir un objeto de otro negocio da 404, porque para ese queryset no existe.

### Crear una ruta (`RouteViewSet.create`)

1. Validar la entrada con `RouteCreateSerializer`.
2. Comprobar el repartidor y que todos los pedidos sean del negocio y estén pendientes.
3. Llamar al optimizador **fuera** de la transacción.
4. En `transaction.atomic()`: `select_for_update()` sobre los pedidos, comprobar otra vez, crear la ruta y las paradas, marcar los pedidos como asignados.

### Cliente del optimizador

Toda falla (red, timeout, status distinto de 200, JSON inválido, ids que no coinciden) se convierte en `OptimizerUnavailable`. La vista la traduce a 502. Los tests usan `httpx.MockTransport` para simular la red sin servidor real.

### Entregar

Idempotente: si `delivered_at` ya tiene valor, no cambia nada. Con `select_for_update` sobre la parada, un doble clic no la marca dos veces.

### Demo

`ensure_demo()` crea el usuario, el negocio y los datos si faltan. `reset_demo()` borra y recrea todo dentro de una transacción. El usuario demo tiene contraseña inutilizable: solo se entra por `/api/auth/demo/`.

**Preguntas**
- ¿Por qué se llama al optimizador antes de abrir la transacción y no dentro?
- ¿Por qué `RouteViewSet.get_queryset` necesita `order_by` explícito si el modelo ya define `ordering`?
- ¿Qué devuelve la API si otro usuario intenta entregar una parada tuya, y por qué ese código y no 403?

---

## 6. El frontend AngularJS

**Archivos:** `frontend/js/app.js`, `js/services/*.js`, `js/controllers/*.js`, `views/*.html`

- **`app.js`:** rutas con `ngRoute` (`#!/pedidos`, …), el interceptor que añade el JWT y vuelve al login ante un 401, y un guard en `$routeChangeStart`.
- **Servicios:**
  - `AuthService`: sesión en `localStorage`, envuelto en `try/catch` por si el navegador lo bloquea.
  - `ApiService`: `$http` más un traductor de errores a mensajes legibles.
  - `MapService`: todo Leaflet. Los textos de usuario se insertan como nodos de texto, nunca como HTML, para evitar XSS.
  - `EngineService`: descarga y compila el wasm una vez.
- **`PlannerController`:** en cada cambio de casilla recalcula la vista previa con `EngineService` y redibuja dos líneas: gris punteada (orden de la lista) y verde (optimizada). Si el wasm no carga, el planificador sigue funcionando sin vista previa.
- `controllerAs: 'vm'`: las vistas usan `vm.algo` en lugar de `$scope.algo`.

**Preguntas**
- ¿Por qué el interceptor obtiene `AuthService` con `$injector.get` y no por inyección directa?
- ¿Qué hace `$q.when(...)` en `EngineService` y por qué hace falta?

---

## 7. Despliegue y CI

**Archivos:** `.github/workflows/ci.yml`, `docs/architecture.md`, `docs/adr/`

- Tres proyectos de Vercel; cada uno usa una carpeta del repo como raíz.
- Vercel detecta Django por `manage.py` y FastAPI por `app/main.py`.
- `.vercelignore` excluye `.venv`, tests y archivos locales del paquete.
- El CI recompila el motor, sube el `.wasm` como artefacto y prueba el optimizador y el frontend **con ese wasm nuevo**, no con el versionado.

**Preguntas**
- Si cambias `route.cpp` y olvidas recompilar el `.wasm`, ¿qué detecta el CI y qué no?
- ¿Qué variables tiene que compartir el backend con el optimizador?

---

## 8. Fotos de evidencia y URLs prefirmadas

**Archivos:** `backend/core/storage.py`, `backend/core/photos.py`, `frontend/js/photo-utils.js`, `frontend/js/services/photo.service.js`, `backend/tests/test_storage.py`, `backend/tests/test_photos.py`

### Qué es una URL prefirmada

Una URL que lleva dentro la firma de nuestras credenciales (`X-Amz-Signature`, `X-Amz-Expires`). Quien la tenga puede hacer **esa** operación (un `PUT` de **ese** objeto con **ese** `Content-Type`) hasta que venza, sin conocer las claves. Así el navegador sube directo al bucket y las claves nunca salen del servidor.

### El flujo

1. `photo.service.js` reduce la imagen con un `canvas` (`RLPhoto.fitWithin`) y la convierte a JPEG.
2. `POST .../photo/upload-url/` → `photos.request_upload()` inventa la clave con un `uuid4` y firma un `PUT` de 5 minutos.
3. El navegador hace el `PUT`. El interceptor de Angular **no** añade el JWT, porque la URL no es de nuestra API: el bucket no debe recibir el token.
4. `POST .../photo/` → `photos.confirm_upload()` valida el nombre de la clave con una expresión regular, bloquea la parada (`select_for_update`), hace `HEAD` y valida tamaño y tipo. Si algo falla, borra el objeto. Si todo va bien, guarda la clave y después borra la foto anterior.
5. El detalle de la ruta trae `photo_url`, un `GET` firmado por 1 hora.

### Lo que corrigió la revisión final

1. **Tamaño firmado:** `presigned_put(key, size)` firma `ContentLength`. El navegador envía `blob.size` al pedir la URL; si sube otra cantidad de bytes, Backblaze responde 403.
2. **Zona temporal:** el navegador sube a `uploads/…`. `confirm_upload` valida y hace `storage.copy()` a `businesses/…`. La URL de subida sigue vigente unos minutos, pero ya no puede tocar la foto confirmada.
3. **Límite:** cada URL entregada crea una fila `UploadGrant`. Con 30 en el último minuto o 200 en el día, la API responde 429. Se cuenta en base de datos porque Vercel corre varias instancias y la memoria no se comparte.
4. **Versiones:** en Backblaze un borrado simple solo oculta el archivo. `_delete_versions()` lista primero todas las versiones y marcadores y luego los borra por `VersionId`. Primero lista y después borra: borrar mientras se pagina se salta objetos (lo detectó el test de 1005 objetos).

### Detalles que vale la pena entender

- `storage.head()` distingue "no existe la foto" de "no existe el bucket": un `HEAD` no trae cuerpo, así que ambos responden 404; ante un 404 se consulta el bucket.
- `request_checksum_calculation="when_required"`: sin esto, `boto3` reciente firma una cabecera CRC32 que Backblaze rechaza en subidas prefirmadas.
- Confirmar dos veces la misma clave no hace nada (doble clic seguro).
- `reset_demo()` borra el prefijo del negocio demo; si el bucket falla, solo lo registra y el reset sigue.
- `moto` intercepta las llamadas de `boto3` y simula S3 en memoria: los tests no usan red ni cuenta.

**Preguntas**
- ¿Por qué el servidor elige la clave del objeto y no el navegador?
- ¿Qué pasaría si se confirmara la foto sin hacer `HEAD`?
- ¿Por qué se borra la foto anterior **después** de guardar la nueva y no antes?
- ¿Qué cambiarías para usar AWS S3 en lugar de Backblaze?
- ¿Por qué no basta con validar el tamaño con `HEAD` al confirmar, si además se firma el tamaño?
- ¿Por qué el límite de subidas no se guarda en la caché en memoria de Django?
