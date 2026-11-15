# ADR 0005: Infraestructura AWS en Terraform, validada en CI sin aplicarse

Fecha: 2026-11-15 · Estado: aceptada

## Contexto

La vacante pide AWS: EC2, S3, RDS e IAM. Desde la fase A, S3 e IAM son código real con `boto3`, contra Backblaze B2. EC2 y RDS solo estaban en una tabla del README. Aplicar la infraestructura en AWS exige una cuenta con tarjeta y genera cobros (unos US$27 al mes), y el demo debe costar $0 y estar siempre disponible.

## Decisión

- Describir RutaLibre en AWS con **Terraform**: módulos `network`, `storage`, `database`, `compute` y `edge` en `infra/terraform/`.
- **No aplicarlo.** El demo sigue en Vercel, Neon y Backblaze.
- Verificarlo en el CI en cada push, sin credenciales: `fmt`, `validate`, TFLint con reglas de AWS, `terraform test` con `mock_provider "aws"`, `shellcheck` y Checkov.
- Los tests fijan propiedades de seguridad concretas: la base de datos no es pública, el puerto 5432 solo se abre al grupo de la aplicación, la política IAM tiene exactamente las acciones que usa el código, todo va por HTTPS.
- Secretos fuera de Terraform: la contraseña de RDS la genera y guarda RDS (`manage_master_user_password`); las claves de Django van en Parameter Store y solo las lee el rol de la instancia.
- Las excepciones de Checkov van en línea, con su razón, y se listan en `infra/README.md`.

## Consecuencias

- Un evaluador ve EC2, RDS, S3 e IAM como código revisable y verificado, no como una promesa.
- Quedan límites honestos: el proveedor simulado no prueba que AWS acepte la configuración, y `bootstrap.sh` nunca se ejecutó. Están escritos en `infra/README.md`.
- Para aplicarlo de verdad faltan tres cambios pequeños en la aplicación (detección de producción, credenciales del rol en `storage.py`, URL de la API en el frontend).
- El job de infraestructura añade unos 2 minutos al CI y corre en paralelo con los demás.

## Alternativas descartadas

- **Solo documentar:** ya existía y no demuestra la habilidad.
- **LocalStack (`apply` contra un AWS simulado):** exige Docker en el CI y RDS y CloudFront no están en su versión gratuita. La fase E lo usará para S3 e IAM.
- **Cuenta de AWS con créditos:** pide tarjeta, los créditos vencen y el demo dejaría de estar disponible.
- **Un solo archivo `.tf`:** más corto, pero no permite probar ni estudiar cada parte por separado.
- **OpenTofu en lugar de Terraform:** compatible, pero Terraform es el nombre que reconoce un reclutador.
