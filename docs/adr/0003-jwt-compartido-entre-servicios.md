# ADR 0003: JWT con clave compartida entre Django y FastAPI

Fecha: 2026-11-13 · Estado: aceptada

## Contexto

El optimizador FastAPI es público en internet y no debe aceptar peticiones anónimas. No tiene base de datos y debe responder rápido.

## Decisión

Django firma los tokens de acceso con HS256 y la clave `JWT_SIGNING_KEY`. FastAPI verifica la firma con esa misma clave, fija el algoritmo a HS256 (no acepta el que diga el token), exige que no esté vencido y que `token_type` sea `access`. Cuando Django llama al optimizador, reenvía el token del usuario que hizo la petición.

## Consecuencias

- El optimizador valida sin consultar la base de datos ni llamar a Django.
- Un test del backend fija el contrato (algoritmo, clave y `token_type`), así que un cambio en Django que lo rompa falla en CI.
- Rotar la clave invalida todas las sesiones y hay que cambiarla en ambos servicios a la vez.
- Cualquiera con un token válido puede usar el optimizador directamente; es aceptable porque solo calcula, no guarda nada.

## Alternativas descartadas

- **RS256 con clave pública:** más correcto si hubiera muchos servicios; para dos es complejidad sin beneficio.
- **API key fija entre servicios:** el navegador no podría probar el optimizador desde `/docs` y la clave no identificaría al usuario.
- **Optimizador sin autenticación:** queda expuesto a abuso.
