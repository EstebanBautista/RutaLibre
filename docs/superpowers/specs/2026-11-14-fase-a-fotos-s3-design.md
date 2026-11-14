# Fase A — Foto de evidencia de entrega en almacenamiento S3

Fecha: 2026-11-14
Estado: aprobado por Esteban (2026-11-14)

## Intención

La vacante pide AWS (S3, IAM). Hoy RutaLibre solo lo documenta. Esta fase lleva S3 a código real:
el repartidor adjunta una foto como evidencia de cada entrega, y la foto se guarda en un bucket
compatible con S3 usando `boto3`, el SDK oficial de AWS. El mismo código funcionaría contra AWS S3
cambiando solo variables de entorno.

## Objetivos

- Adjuntar una foto a una parada de una ruta y verla después en el detalle.
- Subida directa navegador → bucket con **URL prefirmada**; la foto no pasa por las funciones de Vercel.
- Bucket privado. Las fotos solo se ven con URLs prefirmadas de lectura que vencen.
- Costo $0 permanente.
- Tests sin red ni cuenta real, con `moto` (simulador de S3 en Python).

## No-objetivos

- Varias fotos por parada, edición o anotaciones sobre la foto.
- Firma del cliente, geolocalización de la foto.
- Migrar otras piezas a AWS (eso es la Fase B).

## Anti-objetivos

- Que el demo se rompa si el almacenamiento no está configurado o falla: la entrega sin foto
  debe seguir funcionando siempre.
- Que un visitante pueda llenar el bucket gratuito (10 GB).
- Que se pueda ver o reemplazar la foto de otro negocio.
- Claves de almacenamiento en el repositorio o en el navegador.

## Restricciones

- Proveedor: **Backblaze B2** (10 GB gratis, API compatible con S3). Elegido por Esteban.
- Todo lo de la Fase MVP sigue valiendo: costo $0, Vercel + Neon, sin Docker en local.
- Vercel limita el cuerpo de las peticiones a funciones; por eso la subida no pasa por Django.

## Enfoques considerados

| Enfoque | Ventaja | Costo | Decisión |
|---|---|---|---|
| URL prefirmada PUT, navegador → bucket | Patrón estándar de S3; no toca los límites de Vercel; muestra `boto3` e IAM | Requiere CORS en el bucket y un paso de confirmación | **Elegido** |
| Subir la foto a Django y que Django la envíe al bucket | Más simple en el frontend | Choca con el límite de tamaño de Vercel; doble transferencia | Descartado |
| Vercel Blob | Sin cuenta nueva | No es S3 ni `boto3`; no sirve al objetivo | Descartado por Esteban |

## Diseño

### Flujo

1. En el detalle de la ruta, cada parada tiene **"Adjuntar foto"**. Está disponible antes y después
   de marcarla entregada. Adjuntar foto no marca la entrega; son acciones separadas.
2. El navegador reduce la imagen (máximo 1600 px por lado, JPEG calidad 0,8) con un `canvas`.
   Una foto de celular de 4 MB queda en unos 200–400 KB.
3. `POST /api/routes/{id}/stops/{stop_id}/photo/upload-url/` → Django responde
   `{upload_url, key, headers}`. La URL es un PUT prefirmado que vence en 5 minutos, con el
   `Content-Type` fijado a `image/jpeg`.
4. El navegador hace `PUT` de la imagen directo al bucket.
5. `POST /api/routes/{id}/stops/{stop_id}/photo/` con `{key}` → Django confirma con `HEAD` que el
   objeto existe, pesa como máximo 2 MB y es `image/jpeg`; guarda la clave en la parada y borra la
   foto anterior si había. Si el objeto no cumple, lo borra y responde 400.
6. El detalle de la ruta incluye `photo_url` por parada: un GET prefirmado que vence en 1 hora,
   o `null`.

### Datos

- `RouteStop.photo_key` (texto, vacío por defecto) y `RouteStop.photo_uploaded_at` (fecha, nula).
- Clave del objeto: `businesses/{business_id}/routes/{route_id}/stops/{stop_id}/{uuid4}.jpg`.
  Django genera la clave; el cliente no la elige. Al confirmar, Django verifica que la clave
  enviada tenga el prefijo de esa parada.

### Límites

- 1 foto por parada (reemplazar borra la anterior).
- 2 MB máximo por foto, verificado en el servidor con `HEAD`.
- Máximo 200 pedidos por negocio (ya existe) ⇒ como máximo ~400 MB por negocio.
- `Restablecer demo` borra del bucket todos los objetos bajo `businesses/{id_demo}/`.

### Configuración

Variables de entorno del backend (en `.env.example` y en Vercel):

`S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.

Si falta alguna, las fotos quedan desactivadas: `GET /api/business/me/` devuelve
`photos_enabled: false`, el frontend oculta el botón y los endpoints de foto responden 503 con
un mensaje claro. Si el bucket falla en tiempo de ejecución: 502 con mensaje, y la entrega sigue
funcionando.

### Seguridad (lo que se presenta como "IAM")

- Clave de aplicación de B2 limitada a **un solo bucket** y solo a las capacidades necesarias
  (listar, leer, escribir y borrar archivos). Es el equivalente a una política IAM de mínimo
  privilegio, y la documentación lo muestra lado a lado con la política IAM que se usaría en AWS.
- Bucket privado. CORS del bucket permite solo `PUT` y `GET` desde el frontend desplegado y
  `localhost:5500`.
- Las URLs prefirmadas vencen (5 min subida, 1 h lectura).

### Calidad

- Tests del backend con `moto`: URL prefirmada generada, confirmación correcta, objeto ausente,
  objeto demasiado grande, tipo incorrecto, clave de otra parada, reemplazo borra la anterior,
  aislamiento entre negocios, fotos desactivadas sin configuración, fallo del bucket → 502 sin
  romper la entrega, `reset_demo` borra los objetos.
- Prueba manual en el navegador local y en producción.
- README: la fila "AWS" de la tabla de requisitos pasa de "diseño" a S3 con código real; la
  sección "Camino a AWS" muestra la política IAM equivalente.
- `docs/EXPLICACION.md`: sección nueva sobre URLs prefirmadas.

## Valores reales

- Bucket: `rutalibre-evidencias` (privado).
- Endpoint S3: `https://s3.us-east-005.backblazeb2.com`, región `us-east-005`.

## Lo que hace Esteban

1. Crear cuenta en Backblaze B2. Si pide tarjeta y no quiere darla, avisa y se cambia a
   Cloudflare R2 (mismo código, otras variables).
2. Crear un bucket **privado** (nombre sugerido: `rutalibre-evidencias-<algo único>`).
3. Crear una **Application Key** restringida a ese bucket, con permisos de lectura y escritura.
4. Pasar a Claude: nombre del bucket, endpoint S3 (aparece en el bucket, p. ej.
   `s3.us-east-005.backblazeb2.com`), keyID y applicationKey. Las claves van directo al archivo
   `.env.local` ignorado por git, no al chat si es posible (ver plan).

## Decisiones del diseñador

- Foto opcional e independiente de "Marcar entregado".
- Reducción de tamaño en el navegador antes de subir.
- Bucket privado con lecturas prefirmadas de 1 h.
- Confirmación en dos pasos (pedir URL, confirmar) con `HEAD` en el servidor.
- Fotos desactivadas con elegancia si falta configuración.
- `moto` para los tests.

## Lo que queda al constructor

- Nombres exactos de funciones del módulo de almacenamiento.
- Cómo aplicar las reglas CORS del bucket: por API S3 si B2 lo acepta; si no, desde el panel.
- Diseño visual del botón y de la miniatura de la foto.
