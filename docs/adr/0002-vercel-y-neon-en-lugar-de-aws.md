# ADR 0002: Vercel y Neon en lugar de AWS para el demo

Fecha: 2026-11-13 · Estado: aceptada

## Contexto

El proyecto es un portafolio: debe estar disponible siempre y costar $0. En 2026 las cuentas nuevas de AWS reciben créditos que vencen, y S3 ya no tiene capa gratuita permanente. Los PaaS gratuitos con servidor siempre encendido o desaparecieron o duermen el servicio (Render tarda de 30 a 60 s en despertar). Supabase pausa los proyectos gratuitos tras una semana sin uso y hay que reactivarlos a mano.

## Decisión

- Vercel (plan Hobby) para el frontend, la API Django y el optimizador FastAPI.
- Neon (plan gratuito) para PostgreSQL: escala a cero y despierta solo en la primera consulta, sin pausar el proyecto.
- El código no depende de ningún proveedor: Django lee `DATABASE_URL`, y los servicios se comunican por HTTP con URLs configurables.
- La migración a AWS (S3, EC2, RDS, IAM) se documenta en el README y se implementa por fases.

## Consecuencias

- Costo $0 y demo disponible sin intervención.
- Arranque en frío de 1 a 3 s en la primera petición tras inactividad.
- Los requisitos de AWS de la vacante quedan en diseño hasta las fases A y B.

## Alternativas descartadas

- **AWS con capa gratuita:** riesgo de cobro al vencer los créditos.
- **Render, Koyeb, Fly.io, Railway:** el servicio duerme, exigen tarjeta o no tienen plan gratuito.
- **Supabase:** pausa por inactividad.
