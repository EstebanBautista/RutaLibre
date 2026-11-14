# ADR 0004: Fotos de evidencia con URLs prefirmadas en un bucket compatible con S3

Fecha: 2026-11-14 · Estado: aceptada

## Contexto

La vacante pide experiencia con AWS (S3, IAM) y el proyecto solo lo documentaba. Las entregas necesitan una evidencia: una foto por parada. El backend corre en funciones de Vercel, que limitan el tamaño del cuerpo de cada petición, y el proyecto debe costar $0. Una cuenta nueva de AWS no tiene capa gratuita permanente para S3.

## Decisión

- Guardar las fotos en **Backblaze B2** (10 GB gratis) a través de su **API compatible con S3**, con `boto3`, el SDK oficial de AWS.
- Subir en dos pasos: Django firma una **URL PUT prefirmada** de 5 minutos para una clave que elige el servidor; el navegador sube la foto directo al bucket; Django confirma con `HEAD` (existe, ≤ 2 MB, `image/jpeg`) y solo entonces la asocia a la parada.
- El navegador reduce la imagen a 1600 px antes de subirla.
- Bucket privado; lectura con URLs GET prefirmadas de 1 hora.
- Clave de aplicación limitada a ese bucket: el equivalente a una política IAM de mínimo privilegio.
- Tests con `moto`, que simula S3 en memoria.

## Consecuencias

- El mismo código sirve contra AWS S3 cambiando solo variables de entorno.
- Las fotos no consumen ancho de banda ni tiempo de las funciones de Vercel.
- Hay que mantener reglas CORS en el bucket.
- El paso de confirmación evita que un cliente asocie objetos ajenos o archivos enormes.
- Si el almacenamiento falla, solo las fotos se ven afectadas; entregar sigue funcionando.

## Alternativas descartadas

- **Subir la foto a Django y que Django la reenvíe:** choca con el límite de cuerpo de Vercel, duplica la transferencia y alarga cada petición.
- **AWS S3 directo:** sin capa gratuita permanente para cuentas nuevas.
- **Cloudflare R2:** compatible con S3 y gratis, pero varias fuentes indican que pide tarjeta para activarse.
- **Vercel Blob:** no es S3 ni usa `boto3`; no demuestra la habilidad que pide la vacante.
