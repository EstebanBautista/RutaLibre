# RutaLibre — Diseño

Fecha: 2026-11-13
Estado: pendiente de aprobación de Esteban

## 1. Intención y porqué

Esteban va a postularse a la vacante **Desarrollador/a Fullstack Junior** de Partners Digital.
La convocatoria pide Python + Django (modelos, ORM, vistas, DRF), AngularJS (controladores,
servicios, consumo de APIs), AWS (EC2, S3, RDS, IAM), FastAPI (APIs tipadas, validadas y
documentadas), Flask como opcional, y declara que **C++ es un diferencial determinante**.

RutaLibre es el proyecto de portafolio que demuestra ese stack con un caso de uso donde cada
tecnología tiene una razón de existir: una plataforma para que pequeños negocios planifiquen
sus entregas diarias. El negocio registra pedidos con ubicación, el sistema calcula el orden
óptimo de visita y el repartidor marca cada entrega.

El proyecto debe quedar desplegado y público **hoy** (2026-11-13) para adjuntarlo a la
postulación. Después se sigue mejorando por fases.

## 2. Objetivos

- Un demo público que cualquier persona abre y usa sin registrarse, disponible de forma
  permanente y con costo $0.
- Un repositorio público en GitHub (cuenta `EstebanBautista`) con README, diagrama de
  arquitectura, tests y CI en verde.
- Que cada tecnología de la convocatoria aparezca con un uso real y explicable.
- Que el C++ sea visible para quien visita el demo, no solo para quien lee el código.
- Código y documentación que Esteban pueda estudiar después: comentarios donde la lógica no
  es obvia y una guía `docs/EXPLICACION.md`.

## 3. No-objetivos (hoy)

- Rutas por calles reales. Las distancias son en línea recta (haversine).
- Varios vehículos por ruta, ventanas horarias, capacidades.
- Registro público de usuarios. Solo existen el usuario demo y los creados por el admin.
- Pagos, app móvil, tiempo real con websockets.
- Subida de fotos, Terraform, LocalStack y Flask. Están en las fases posteriores (sección 9).

## 4. Anti-objetivos

El proyecto fracasa, aunque funcione, si:

- El demo está caído, pide registro, o necesita reactivación manual tras días sin uso.
- Genera cualquier cobro.
- El C++ parece decorativo.
- El README promete algo que el demo no hace. Lo que no está construido se presenta como
  "siguiente versión", nunca como hecho.

## 5. Restricciones

- **Costo $0 permanente.** Sin AWS real. Sin servicios que pausen el proyecto por inactividad
  (por eso se descartó Supabase).
- **Todo el proyecto vive en `I:\proyecto_trabajo`.** El disco C tiene poco espacio: entornos
  virtuales, emsdk y `node_modules` van en I:.
- **Docker no está en ejecución** en la máquina de Esteban. El desarrollo local no debe
  depender de Docker.
- Máquina: Windows 10, Python 3.12.6, Node 24, git, cmake 4.4, `gh` autenticado.
  `g++` local es MinGW 6.3 (antiguo); no se usa para compilar el motor.
- Entrega hoy. Ante una duda entre completo y desplegado, gana desplegado.

## 6. Arquitectura

Monorepo con cuatro piezas y tres proyectos de Vercel.

```
rutalibre/
  engine/      Motor de rutas en C++17. Se compila a WebAssembly.
  backend/     Django 5.2 + DRF. API principal y admin.        -> proyecto Vercel 1
  optimizer/   FastAPI. Servicio de optimización.               -> proyecto Vercel 2
  frontend/    AngularJS 1.8, estático, sin paso de build.      -> proyecto Vercel 3
  docs/        Arquitectura, ADRs, guía de explicación.
  .github/workflows/ci.yml
```

Base de datos: **Neon Postgres** (plan gratis; escala a cero y despierta sola).
En local, Django usa SQLite cuando no hay `DATABASE_URL`.

### 6.1 Motor C++ (`engine/`)

- C++17, sin dependencias externas, sin E/S. CMake.
- Algoritmos:
  - distancia haversine entre dos coordenadas;
  - matriz de distancias;
  - ruta inicial por vecino más cercano (nearest neighbor) partiendo del depósito;
  - mejora por 2-opt hasta que no haya mejora;
  - longitud de una ruta dada (sirve para medir la ruta "ingenua", en el orden de llegada
    de los pedidos).
- La ruta es un circuito: sale del depósito, visita todas las paradas y vuelve al depósito.
- Interfaz: funciones C (`extern "C"`) sobre memoria lineal, para que el mismo binario sirva
  en navegador y en servidor. Como mínimo: reservar y liberar memoria, optimizar (entra un
  arreglo de coordenadas, sale el orden y la distancia total en km) y medir una ruta.
- Un solo artefacto `engine.wasm`, compilado con Emscripten en modo independiente
  (standalone), sin "glue" de JavaScript. Se copia a `frontend/` y a `optimizer/`.
- Emscripten se instala con **emsdk dentro de `I:\proyecto_trabajo\.tools\emsdk`** (ignorado
  por git). Decisión del diseñador: evita Docker y el disco C.
- El `.wasm` compilado **se versiona en el repo**. Así Vercel no necesita compilar C++.
  El CI lo recompila y ejecuta los tests para probar que el fuente y el binario coinciden
  en comportamiento.
- Tests: casos pequeños con resultado conocido (0, 1, 2 paradas; cuadrado; puntos en línea;
  la ruta optimizada nunca es más larga que la ingenua). Se ejecutan compilados a wasm y
  corridos con Node, y de forma nativa en el CI (Ubuntu, g++ moderno).

### 6.2 Optimizador (`optimizer/`, FastAPI)

- `POST /optimize`: recibe depósito y lista de paradas (`id`, `lat`, `lng`); devuelve el
  orden de ids, la distancia optimizada y la distancia ingenua, en km.
- `GET /health`.
- Modelos Pydantic con validación: latitud y longitud en rango, entre 1 y 100 paradas,
  ids únicos. Los errores salen como 422 con detalle.
- Carga `engine.wasm` con `wasmtime` una vez por proceso y lo reutiliza.
- Exige `Authorization: Bearer <JWT>` y verifica la firma con la misma clave que usa Django.
  No consulta la base de datos.
- Documentación OpenAPI en `/docs`, enlazada desde el README y desde el frontend.

### 6.3 Backend (`backend/`, Django + DRF)

- Autenticación JWT (`djangorestframework-simplejwt`, HS256).
- Modelos:
  - `Business`: dueño (User), nombre, depósito (`lat`, `lng`).
  - `Driver`: negocio, nombre, teléfono.
  - `Order`: negocio, cliente, dirección (texto), `lat`, `lng`, notas,
    estado (`pending`, `assigned`, `delivered`), fecha de creación.
  - `Route`: negocio, repartidor, fecha, estado (`planned`, `in_progress`, `done`),
    `total_km`, `naive_km`.
  - `RouteStop`: ruta, pedido, secuencia, `delivered_at`.
- Todo dato se filtra por el negocio del usuario autenticado. Un usuario nunca ve datos de
  otro negocio.
- Endpoints (prefijo `/api/`):
  - `auth/token/`, `auth/token/refresh/`, `auth/demo/` (devuelve un JWT del usuario demo).
  - CRUD de `orders/` y `drivers/`.
  - `routes/`: al crear, recibe repartidor e ids de pedidos pendientes; **Django llama al
    optimizador**, guarda las paradas en el orden devuelto y marca los pedidos como
    asignados. Todo dentro de una transacción.
  - `routes/{id}/stops/{stop_id}/deliver/`: marca una parada como entregada. Al entregar la
    última, la ruta pasa a `done`.
  - `demo/reset/`: restablece los datos del negocio demo.
  - `business/me/`: datos del negocio y su depósito.
- Si el optimizador no responde (timeout de 10 s) o falla, crear la ruta devuelve 502 con
  un mensaje claro y no deja datos a medias.
- Admin de Django activo, con archivos estáticos servidos por WhiteNoise.
- Comando `seed_demo`: crea el usuario demo, su negocio con depósito en Cali, 3 repartidores
  y unos 12 pedidos en barrios de Cali. Es idempotente.
- Tests con pytest: aislamiento entre negocios, creación de ruta con el optimizador
  simulado (mock), fallo del optimizador, entrega de paradas, login demo.

### 6.4 Frontend (`frontend/`, AngularJS 1.8)

- Estático, sin bundler ni paso de build. AngularJS, `angular-route` y Leaflet se incluyen
  como archivos dentro del repo (sin depender de un CDN). Mapa con teselas de OpenStreetMap.
- Estructura clásica de AngularJS: módulos, controladores, servicios (`AuthService`,
  `OrderService`, `RouteService`, `EngineService`), un interceptor HTTP que añade el JWT y
  redirige al login ante un 401.
- Vistas:
  - **Login**: usuario y contraseña, y un botón grande "Entrar al demo".
  - **Pedidos**: lista y formulario. La ubicación se fija haciendo clic en el mapa.
  - **Planificar ruta**: se eligen pedidos pendientes y repartidor. El mapa dibuja la ruta
    ingenua y la optimizada, con los km de cada una y el ahorro. Esta vista previa la
    calcula `engine.wasm` **en el navegador**, al instante. Al confirmar, se crea la ruta en
    el backend.
  - **Rutas**: lista y detalle con mapa, paradas en orden y botón "Marcar entregado".
- Un pie o sección "Cómo está hecho" con enlaces al repo, a la documentación OpenAPI del
  optimizador y una frase que dice que el cálculo corre en C++ compilado a WebAssembly.
- Interfaz en español. Diseño limpio y propio, usable en móvil.

### 6.5 Flujo principal

1. El visitante pulsa "Entrar al demo". El frontend recibe un JWT de Django.
2. En "Planificar ruta" elige pedidos. El navegador ejecuta el motor C++ y muestra la
   comparación sin esperar al servidor.
3. Al confirmar, Django valida, llama a FastAPI con el JWT del usuario, FastAPI ejecuta el
   mismo motor C++ y Django guarda la ruta. El servidor no confía en el cálculo del
   navegador.
4. En el detalle de la ruta se marcan las entregas.

### 6.6 Despliegue

- Tres proyectos de Vercel (plan Hobby) sobre el mismo repo, cada uno con su "Root
  Directory": `backend`, `optimizer`, `frontend`. Despliegue automático al hacer push a
  `main`.
- Variables de entorno: `DATABASE_URL`, `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY` (igual en
  backend y optimizer), `OPTIMIZER_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`.
  Ningún secreto se sube al repo; hay un `.env.example` por servicio.
- CORS: backend y optimizer aceptan solo el origen del frontend desplegado y `localhost`.
- Migraciones y `seed_demo` se ejecutan contra Neon desde la máquina local durante el
  despliegue inicial.
- El constructor debe verificar contra la documentación vigente de Vercel la configuración
  exacta para Django y FastAPI antes de escribirla.

### 6.7 Calidad

- GitHub Actions en cada push y PR: tests del backend, tests del optimizador, compilación y
  tests del motor.
- README en español: qué es, enlace al demo, captura, diagrama de arquitectura, tabla
  "requisito de la convocatoria → dónde está en el proyecto", cómo correrlo en local,
  sección "Camino a AWS" y hoja de ruta.
- `docs/adr/`: decisiones cortas (por qué WebAssembly, por qué Vercel + Neon y no AWS real,
  por qué JWT compartido).
- `docs/EXPLICACION.md`: recorrido guiado del código para estudiarlo.

## 7. AWS: cómo se presenta hoy

Hoy AWS aparece solo como documentación: la sección "Camino a AWS" mapea cada pieza a su
servicio (frontend → S3 + CloudFront; backend y optimizador → EC2 o contenedores;
Neon → RDS PostgreSQL; fotos → S3; permisos → roles IAM de mínimo privilegio). El README lo
dice con honestidad: el demo corre en servicios gratuitos por una decisión de costo, y el
código de AWS llega en las fases A y B.

## 8. Decisiones tomadas por el diseñador

Esteban delegó la arquitectura. Estas decisiones son del diseñador y Esteban puede cambiarlas:

- Nombre RutaLibre y caso de uso de entregas.
- Vercel + Neon como plataforma gratuita.
- Motor C++ compilado a un único WebAssembly, usado en navegador y servidor.
- emsdk instalado en I: en lugar de Docker; `.wasm` versionado en el repo.
- Django orquesta la llamada al optimizador (no el navegador).
- JWT HS256 con clave compartida entre Django y FastAPI.
- AngularJS sin bundler, librerías dentro del repo.
- Ubicación por clic en el mapa, sin geocodificación.
- Botón de restablecer el demo, porque cualquier visitante puede modificar sus datos.
- Código e identificadores en inglés; interfaz y documentación en español.
- SQLite en local, Postgres en producción.

Aprobado por Esteban: costo $0 con alternativas gratuitas, el recorte para hoy, la ruta
`I:\proyecto_trabajo`, y seguir mejorando por fases.

## 9. Fases posteriores (si sobra tiempo hoy, o desde mañana)

En orden de valor para la convocatoria:

- **Fase A — S3 con boto3.** Foto de evidencia al entregar. Subida con URL prefirmada.
  Almacenamiento compatible con S3, gratuito y sin pausa por inactividad (candidato:
  Backblaze B2; verificar condiciones antes de elegir). Cubre "S3" con código real.
- **Fase B — Terraform.** `infra/aws/` con EC2, RDS, S3 e IAM de mínimo privilegio.
  Se valida en CI con `terraform validate`; no se aplica. Cubre EC2, RDS e IAM.
- **Fase C — Flask.** Microservicio pequeño de notificaciones (webhook al completar una
  ruta). Cubre el requisito opcional.
- **Fase D — Producto.** Vista propia del repartidor, registro de usuarios, edición del
  depósito.
- **Fase E — LocalStack.** Emular S3 e IAM en local con políticas versionadas.
- **Fase F — Calles reales.** Distancias por carretera con un servicio de enrutamiento
  abierto.

Cada fase pasa por su propio diseño corto y plan antes de construirse.

## 10. Lo que queda al constructor

- Firmas exactas de las funciones del motor y formato de los arreglos en memoria.
- Banderas de compilación de Emscripten y cómo se instancia el wasm en navegador y wasmtime.
- Versiones exactas de dependencias (Django 5.2 LTS, AngularJS 1.8.3 como referencia).
- Configuración de Vercel por servicio, verificada con su documentación vigente.
- Diseño visual del frontend.
- Estructura interna de apps de Django y de módulos de AngularJS.
- Coordenadas y nombres de los datos de demostración.
