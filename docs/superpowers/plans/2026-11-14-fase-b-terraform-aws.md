# Fase B — Infraestructura AWS en Terraform: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Describir RutaLibre en AWS (EC2, RDS, S3, IAM, CloudFront) con Terraform y verificarlo en el CI sin credenciales ni `apply`.

**Architecture:** Cinco módulos (`network`, `storage`, `database`, `compute`, `edge`) y un módulo raíz en `infra/terraform/`. Los tests (`terraform test`) viven en `infra/terraform/tests/`, usan `mock_provider "aws"` y cargan cada módulo con `module { source = ... }` dentro del bloque `run`, así que basta un solo `terraform init` en la raíz. Un job nuevo del CI ejecuta formato, validación, TFLint, tests, shellcheck y Checkov.

**Tech Stack:** Terraform 1.17.2, proveedor `hashicorp/aws` 6.x (bloqueado en 6.73.0), TFLint 0.66.0 + `tflint-ruleset-aws` 0.50.0, Checkov 3.4.5, shellcheck, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-14-fase-b-terraform-aws-design.md`

## Global Constraints

- **Nunca** ejecutar `terraform apply`, `terraform plan` contra AWS real, ni configurar credenciales de AWS. Solo `fmt`, `init -backend=false`, `validate`, `test`.
- No modificar `backend/`, `optimizer/`, `frontend/` ni `engine/`.
- Herramientas locales en `I:\proyecto_trabajo\.tools\` (ya ignorado por git). Nada se instala en C:. Para pip: `PIP_CACHE_DIR=I:\proyecto_trabajo\.tools\pip-cache`.
- Las descargas (Terraform, TFLint, proveedor AWS ≈ 700 MB descomprimido) requieren el visto bueno de Esteban; verificar el SHA256 de cada binario contra el archivo de sumas publicado.
- Versiones: Terraform `1.17.2`; `required_version = ">= 1.11, < 2.0"`; `aws = "~> 6.0"`; TFLint `v0.66.0`; ruleset AWS `0.50.0`; Checkov `3.4.5`; `hashicorp/setup-terraform@v4`; `terraform-linters/setup-tflint@v6`.
- Región `us-east-1`; zonas `us-east-1a`, `us-east-1b`; prefijo de nombres `rutalibre-prod`.
- CIDR: VPC `10.20.0.0/16`; públicas `10.20.0.0/24`, `10.20.1.0/24`; privadas `10.20.10.0/24`, `10.20.11.0/24`.
- Ningún valor secreto en `.tf`, en variables con valor por defecto ni en el estado.
- Tests: `command = plan` siempre. Las aserciones solo leen valores **conocidos durante el plan** (atributos configurados), nunca atributos calculados por AWS. Un atributo opcional que AWS también calcula (`multi_az`, `storage_type`, `associate_public_ip_address`…) es desconocido si no se escribe: el módulo lo fija **explícitamente**. Si una aserción falla con "unknown value", se fija el atributo en el módulo; no se usa `override_during = plan` salvo donde este plan lo indica.
- Políticas IAM y de bucket con `jsonencode(...)`, no con `data "aws_iam_policy_document"` (con el proveedor simulado devuelve una cadena aleatoria). Los ARN de S3 se construyen del nombre: `"arn:aws:s3:::${name}"`.
- Excepciones de Checkov solo en línea (`#checkov:skip=ID:razón`) junto al recurso. Prohibido un archivo global de exclusiones y `--soft-fail`.
- Código, nombres y comentarios en inglés; documentación en español.
- `git push` despliega Vercel: empujar solo con el CI local en verde. Esta fase no tiene migraciones.

## Review Focus

1. **Un test que pasa aunque la propiedad se rompa.** Con el proveedor simulado es fácil afirmar sobre un valor desconocido o trivial. Cada tarea incluye una prueba de mutación: romper la propiedad a mano, ver el test fallar, revertir. Tareas 2–5.
2. **Archivo de bloqueo generado en Windows que falla en Linux.** `terraform init -lockfile=readonly` en el CI falla si `.terraform.lock.hcl` solo trae hashes de `windows_amd64`. Tarea 1 lo genera con `terraform providers lock -platform=windows_amd64 -platform=linux_amd64`.
3. **Política IAM que no coincide con el código.** `storage.py` llama `list_object_versions` y borra por `VersionId`; sin `s3:ListBucketVersions` y `s3:DeleteObjectVersion` el borrado fallaría en AWS. Tarea 4 afirma el conjunto exacto de acciones; Tarea 6 corrige el README.
4. **Excepción de Checkov sin razón, o hallazgo corregible exceptuado.** Tarea 6: cada excepción lleva razón y aparece en la tabla de `infra/README.md`; el job falla ante un hallazgo nuevo.
5. **Alguien lee el README y cree que está desplegado en AWS, o ejecuta `apply` sin saber el costo.** Tarea 6: "validado, no aplicado" en README e `infra/README.md`, con costo estimado y lista de lo que falta.

## Archivos

```
infra/README.md                         Qué es, cómo validar en local, límites, costo, excepciones
infra/terraform/
  versions.tf                           required_version, required_providers
  providers.tf                          provider "aws" (region, default_tags)
  variables.tf  main.tf  outputs.tf     Raíz: conecta los módulos
  backend.tf.example                    Backend S3 con use_lockfile (no activo)
  .tflint.hcl                           Plugin aws 0.50.0
  .terraform.lock.hcl                   Hashes windows_amd64 y linux_amd64
  modules/network/   {main,variables,outputs,versions}.tf
  modules/storage/   {main,variables,outputs,versions}.tf
  modules/database/  {main,variables,outputs,versions}.tf
  modules/compute/   {main,iam,variables,outputs,versions}.tf, files/bootstrap.sh
  modules/edge/      {main,variables,outputs,versions}.tf
  tests/{network,storage,database,compute,edge,stack}.tftest.hcl
.github/workflows/ci.yml                Job "infra"
.gitignore                              .terraform/, *.tfstate*, *.tfplan
README.md, docs/architecture.md, docs/EXPLICACION.md, docs/adr/0005-*.md
```

Cabecera común de cada `tests/*.tftest.hcl`:

```hcl
mock_provider "aws" {}
```

y cada bloque `run` de un módulo usa `command = plan` y `module { source = "./modules/<nombre>" }`.

Cada módulo lleva su `versions.tf` (`required_version` y `required_providers` iguales a los de la raíz): TFLint lo exige y, en modo `--recursive`, entra a cada carpeta; por eso recibe la ruta absoluta de la configuración.

---

### Task 1: Herramientas, esqueleto, CI y módulo `network`

**Files:**
- Create: `infra/terraform/{versions,providers,variables,main,outputs}.tf`, `.tflint.hcl`, `.terraform.lock.hcl`, `backend.tf.example`
- Create: `infra/terraform/modules/network/{main,variables,outputs,versions}.tf`, `infra/terraform/tests/network.tftest.hcl`
- Modify: `.gitignore`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces — módulo `network`:
  - variables: `name_prefix` (string), `vpc_cidr` (string), `availability_zones` (list(string), 2 elementos), `public_subnet_cidrs` (list(string)), `private_subnet_cidrs` (list(string))
  - recursos con nombre fijo: `aws_vpc.this`, `aws_subnet.public` y `aws_subnet.private` (ambos con `count`), `aws_default_security_group.this`
  - outputs: `vpc_id`, `vpc_cidr`, `public_subnet_ids`, `private_subnet_ids`
- Produces — raíz: variables `project` (`"rutalibre"`), `environment` (`"prod"`), `region`, `availability_zones`, `vpc_cidr`; `local.name_prefix = "${var.project}-${var.environment}"`; `module.network`.

- [ ] **Step 1: Instalar herramientas en `.tools/`** (tras el visto bueno de Esteban). Terraform 1.17.2 `windows_amd64` de `releases.hashicorp.com` a `.tools/terraform/`; TFLint v0.66.0 de GitHub Releases a `.tools/tflint/`; Checkov 3.4.5 con `python -m venv .tools/checkov-venv` y pip. Verificar SHA256.
  Run: `.tools/terraform/terraform.exe version` → `Terraform v1.17.2`; `.tools/tflint/tflint.exe --version` → `0.66.0`; `.tools/checkov-venv/Scripts/checkov --version` → `3.4.5`.

- [ ] **Step 2: Añadir a `.gitignore`** `.terraform/`, `*.tfstate`, `*.tfstate.*`, `*.tfplan`, `crash.log`.

- [ ] **Step 3: Escribir el test que falla** `tests/network.tftest.hcl`:

```hcl
mock_provider "aws" {}

run "network_layout" {
  command = plan
  module { source = "./modules/network" }
  variables {
    name_prefix          = "rutalibre-test"
    vpc_cidr             = "10.20.0.0/16"
    availability_zones   = ["us-east-1a", "us-east-1b"]
    public_subnet_cidrs  = ["10.20.0.0/24", "10.20.1.0/24"]
    private_subnet_cidrs = ["10.20.10.0/24", "10.20.11.0/24"]
  }
  assert {
    condition     = aws_vpc.this.cidr_block == "10.20.0.0/16" && aws_vpc.this.enable_dns_hostnames
    error_message = "VPC must use the given CIDR with DNS hostnames enabled."
  }
  assert {
    condition     = length(aws_subnet.public) == 2 && length(aws_subnet.private) == 2
    error_message = "Expected two public and two private subnets."
  }
  assert {
    condition     = aws_subnet.private[*].cidr_block == ["10.20.10.0/24", "10.20.11.0/24"] && aws_subnet.private[*].availability_zone == ["us-east-1a", "us-east-1b"]
    error_message = "Private subnets must cover both zones with the given CIDRs."
  }
  assert {
    condition     = alltrue([for s in concat(aws_subnet.public, aws_subnet.private) : s.map_public_ip_on_launch == false])
    error_message = "No subnet may auto-assign public IPs."
  }
}
```

- [ ] **Step 4: Escribir `versions.tf`, `providers.tf` (con `default_tags`: `Project`, `Environment`, `ManagedBy = "terraform"`) y `.tflint.hcl`.**
  Run (en `infra/terraform`): `terraform init -backend=false; terraform test` → FALLA: no existe `./modules/network` (el fallo puede salir ya en `init`).

- [ ] **Step 5: Implementar `modules/network`.** VPC, IGW, 2+2 subredes con `count`, tabla de rutas pública con `aws_route` a `0.0.0.0/0`, tabla privada **sin** ruta por defecto, asociaciones, `aws_default_security_group` sin reglas (lo comprueba Checkov en la Tarea 6: sus reglas son desconocidas durante el plan). Sin NAT. Un validador en `availability_zones` exige exactamente 2 y la misma longitud que las listas de CIDR.

- [ ] **Step 6: Conectar `module.network` en la raíz** (`variables.tf`, `main.tf`, `outputs.tf` con `vpc_id`) y generar el bloqueo para las dos plataformas.
  Run: `terraform init -backend=false && terraform providers lock -platform=windows_amd64 -platform=linux_amd64` → `.terraform.lock.hcl` con hashes de ambas.
  Run: `terraform fmt -check -recursive && terraform validate && terraform test && tflint --init && tflint --recursive --config "$(pwd)/.tflint.hcl"` → todo en verde, `1 passed, 0 failed`.

- [ ] **Step 7: Escribir `backend.tf.example`** (backend `s3`, `encrypt = true`, `use_lockfile = true`, comentario: no activo porque esta infraestructura no se aplica).

- [ ] **Step 8: Añadir el job `infra` a `.github/workflows/ci.yml`**, nombre "Infraestructura (Terraform)", `working-directory: infra/terraform`, sin `needs`. Pasos: checkout; `hashicorp/setup-terraform@v4` (`terraform_version: 1.17.2`, `terraform_wrapper: false`); `terraform fmt -check -recursive`; `terraform init -backend=false -lockfile=readonly`; `terraform validate`; `terraform-linters/setup-tflint@v6` (`tflint_version: v0.66.0`); `tflint --init` (con `GITHUB_TOKEN`); `tflint --recursive --config "$(pwd)/.tflint.hcl"`; `terraform test`. Shellcheck y Checkov se añaden en las tareas 4 y 6.

- [ ] **Step 9: Commit y push; comprobar el job en verde.**
  `git commit -m "feat(infra): Terraform skeleton, network module and CI job"`
  Run: `gh run watch` → los 5 jobs en verde.

---

### Task 2: Módulo `storage`

**Files:**
- Create: `infra/terraform/modules/storage/{main,variables,outputs,versions}.tf`, `infra/terraform/tests/storage.tftest.hcl`
- Modify: `infra/terraform/{variables,main,outputs}.tf`

**Interfaces:**
- Produces — módulo `storage`:
  - variables: `evidence_bucket_name` (string), `frontend_bucket_name` (string), `cors_allowed_origins` (list(string))
  - recursos: `aws_s3_bucket.evidence`, `aws_s3_bucket.frontend`; y por bucket `aws_s3_bucket_public_access_block.<n>`, `aws_s3_bucket_versioning.<n>`, `aws_s3_bucket_server_side_encryption_configuration.<n>`, `aws_s3_bucket_ownership_controls.<n>`; solo evidencias: `aws_s3_bucket_cors_configuration.evidence`, `aws_s3_bucket_lifecycle_configuration.evidence`, `aws_s3_bucket_policy.evidence`
  - outputs: `evidence_bucket_name`, `evidence_bucket_arn` (= `"arn:aws:s3:::${var.evidence_bucket_name}"`), `frontend_bucket_id`, `frontend_bucket_arn` (construido igual), `frontend_bucket_regional_domain_name`
- Raíz: variables `evidence_bucket_name` (por defecto `"rutalibre-evidencias"`), `frontend_bucket_name` (`"rutalibre-frontend"`), `cors_allowed_origins`.

- [ ] **Step 1: Test que falla** `tests/storage.tftest.hcl`, un `run "buckets_are_private"` con `evidence_bucket_name = "ev-test"`, `frontend_bucket_name = "fe-test"`, `cors_allowed_origins = ["https://example.test"]`. Aserciones:
  - para `evidence` y `frontend`: los cuatro campos de `aws_s3_bucket_public_access_block` (`block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets`) son `true`;
  - `aws_s3_bucket_versioning.<n>.versioning_configuration[0].status == "Enabled"` en ambos;
  - `aws_s3_bucket_ownership_controls.<n>.rule[0].object_ownership == "BucketOwnerEnforced"` en ambos;
  - CORS de evidencias: una sola regla; `toset(allowed_methods) == toset(["PUT", "GET"])`; `toset(allowed_origins) == toset(["https://example.test"])`;
  - ciclo de vida: existe una regla con `filter[0].prefix == "uploads/"`, `status == "Enabled"` y `expiration[0].days == 1`;
  - política de evidencias: `jsondecode(aws_s3_bucket_policy.evidence.policy)` contiene una sentencia `Effect = "Deny"` con `Condition.Bool["aws:SecureTransport"] == "false"`;
  - `output.evidence_bucket_arn == "arn:aws:s3:::ev-test"`.

- [ ] **Step 2:** Run `terraform test -filter=tests/storage.tftest.hcl` → FALLA (módulo inexistente).

- [ ] **Step 3: Implementar `modules/storage`.** Cifrado `AES256`. Ciclo de vida de evidencias con tres reglas: `expire-uploads` (prefijo `uploads/`, 1 día), `expire-noncurrent` (`noncurrent_version_expiration` 1 día y `expired_object_delete_marker = true`), `abort-multipart` (1 día). Cabeceras CORS: copiar las vigentes en `.tools/scripts/b2_cors.py`. El bucket `frontend` **no** lleva política aquí (la pone `edge`).

- [ ] **Step 4:** Conectar en la raíz. Run: `terraform fmt -check -recursive && terraform validate && terraform test && tflint --recursive --config "$(pwd)/.tflint.hcl"` → verde.

- [ ] **Step 5: Prueba de mutación.** Poner `restrict_public_buckets = false` en `evidence` → `terraform test` FALLA en esa aserción. Revertir. Quitar `"PUT"` del CORS → FALLA. Revertir.

- [ ] **Step 6: Commit.** `feat(infra): private S3 buckets for evidence photos and frontend`

---

### Task 3: Módulo `database`

**Files:**
- Create: `infra/terraform/modules/database/{main,variables,outputs,versions}.tf`, `infra/terraform/tests/database.tftest.hcl`

**Interfaces:**
- Consumes: `module.network.vpc_id`, `module.network.private_subnet_ids`; `app_security_group_id` (lo produce la Tarea 4).
- Produces — módulo `database`:
  - variables: `name_prefix`, `vpc_id`, `subnet_ids` (list(string)), `app_security_group_id` (string), `instance_class` (por defecto `"db.t4g.micro"`), `allocated_storage` (20), `engine_version` (`"17"`), `db_name` (`"rutalibre"`), `username` (`"rutalibre"`)
  - recursos: `aws_db_instance.this`, `aws_db_subnet_group.this`, `aws_db_parameter_group.this`, `aws_security_group.db`, `aws_vpc_security_group_ingress_rule.from_app`
  - outputs: `address`, `port`, `db_name`, `master_user_secret_arn`, `security_group_id`
- Raíz: hasta la Tarea 4, `main.tf` **no** llama a `module.database` (le falta `app_security_group_id`). Esta tarea solo entrega el módulo y su test.

- [ ] **Step 1: Test que falla** `tests/database.tftest.hcl`, `run "database_is_private"` con `vpc_id = "vpc-test"`, `subnet_ids = ["subnet-a", "subnet-b"]`, `app_security_group_id = "sg-app"`. Aserciones sobre `aws_db_instance.this`:
  - `engine == "postgres"`, `instance_class == "db.t4g.micro"`, `allocated_storage == 20`, `storage_type == "gp3"`;
  - `publicly_accessible == false`, `storage_encrypted == true`, `multi_az == false`;
  - `manage_master_user_password == true` y `password == null`;
  - `deletion_protection == true`, `skip_final_snapshot == false`, `backup_retention_period == 7`;
  y sobre `aws_vpc_security_group_ingress_rule.from_app`:
  - `from_port == 5432`, `to_port == 5432`, `ip_protocol == "tcp"`;
  - `referenced_security_group_id == "sg-app"`, `cidr_ipv4 == null`, `cidr_ipv6 == null`;
  y `aws_db_parameter_group.this` contiene el parámetro `rds.force_ssl` con valor `"1"`.

- [ ] **Step 2:** Run `terraform test -filter=tests/database.tftest.hcl` → FALLA.

- [ ] **Step 3: Implementar `modules/database`.** Familia del grupo de parámetros `postgres17`. `final_snapshot_identifier = "${var.name_prefix}-final"`, `copy_tags_to_snapshot = true`, `auto_minor_version_upgrade = true`. El grupo de seguridad `db` no declara reglas de salida.

- [ ] **Step 4:** Run: `terraform fmt -check -recursive && terraform validate && terraform test && tflint --recursive --config "$(pwd)/.tflint.hcl"` → verde.

- [ ] **Step 5: Prueba de mutación.** `publicly_accessible = true` → FALLA. Revertir. Cambiar la regla a `cidr_ipv4 = "0.0.0.0/0"` → FALLA. Revertir.

- [ ] **Step 6: Commit.** `feat(infra): private RDS PostgreSQL with managed master password`

---

### Task 4: Módulo `compute` (EC2, rol IAM, arranque)

**Files:**
- Create: `infra/terraform/modules/compute/{main,iam,variables,outputs,versions}.tf`, `modules/compute/files/bootstrap.sh`, `infra/terraform/tests/compute.tftest.hcl`
- Modify: `infra/terraform/{variables,main,outputs}.tf`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `module.network.{vpc_id,vpc_cidr,public_subnet_ids}`; `module.storage.{evidence_bucket_name,evidence_bucket_arn}`; `module.database.{address,port,db_name,master_user_secret_arn}`.
- Produces — módulo `compute`:
  - variables: `name_prefix`, `region`, `vpc_id`, `vpc_cidr`, `subnet_id`, `instance_type` (por defecto `"t3.micro"`), `evidence_bucket_name`, `evidence_bucket_arn`, `db_secret_arn`, `db_address`, `db_port`, `db_name`, `config_parameter_path` (por defecto `"/rutalibre/prod"`), `repo_url`, `app_git_ref` (`"main"`)
  - recursos: `aws_instance.app`, `aws_eip.app`, `aws_security_group.app`, `aws_vpc_security_group_ingress_rule.http_from_cloudfront`, `aws_iam_role.app`, `aws_iam_instance_profile.app`, `aws_iam_role_policy.evidence_photos`, `aws_iam_role_policy.read_config`, `aws_iam_role_policy.read_db_secret`, `aws_iam_role_policy_attachment.ssm`
  - outputs: `security_group_id`, `public_dns` (del EIP), `instance_id`, `role_name`
- Raíz: ahora sí `module.database` (con `app_security_group_id = module.compute.security_group_id`) y `module.compute`.

- [ ] **Step 1: Test que falla** `tests/compute.tftest.hcl`, `run "instance_is_hardened"` y `run "iam_is_least_privilege"`, con `evidence_bucket_arn = "arn:aws:s3:::ev-test"` y el resto de variables con valores de prueba. Aserciones:
  - `aws_instance.app`: `instance_type == "t3.micro"`; `metadata_options[0].http_tokens == "required"`; `root_block_device[0].encrypted == true`; `associate_public_ip_address == false` (`key_name` no se afirma: sin escribirlo es desconocido durante el plan; lo cubre el paso 7);
  - `aws_vpc_security_group_ingress_rule.http_from_cloudfront`: `from_port == 80`, `to_port == 80`, `cidr_ipv4 == null`, `cidr_ipv6 == null`;
  - confianza del rol: `jsondecode(aws_iam_role.app.assume_role_policy).Statement[0].Principal.Service == "ec2.amazonaws.com"`;
  - sobre `jsondecode(aws_iam_role_policy.evidence_photos.policy).Statement`:
    - la sentencia cuyo `Resource` es `"arn:aws:s3:::ev-test/*"` tiene `toset(Action) == toset(["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:DeleteObjectVersion"])`;
    - la sentencia cuyo `Resource` es `"arn:aws:s3:::ev-test"` tiene `toset(Action) == toset(["s3:ListBucket", "s3:ListBucketVersions"])`;
    - hay exactamente 2 sentencias, ambas `Effect = "Allow"`, y ningún `Action` ni `Resource` es `"*"` ni contiene `"s3:*"`;
  - `aws_iam_role_policy_attachment.ssm.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"`.

- [ ] **Step 2:** Run `terraform test -filter=tests/compute.tftest.hcl` → FALLA.

- [ ] **Step 3: Implementar `iam.tf`.** Tres `aws_iam_role_policy` con `jsonencode`. `read_config`: `ssm:GetParametersByPath` y `ssm:GetParameters` sobre `arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.config_parameter_path}/*`. `read_db_secret`: `secretsmanager:GetSecretValue` sobre `var.db_secret_arn`. Comprobar en la documentación de AWS si leer un `SecureString` cifrado con la clave `aws/ssm` exige `kms:Decrypt` explícito; añadirlo solo si hace falta, limitado con `kms:ViaService`.

- [ ] **Step 4: Implementar `main.tf`.** AMI con `data "aws_ssm_parameter"` en `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64`. Grupo de seguridad: entrada 80 con `prefix_list_id` de `data "aws_ec2_managed_prefix_list"` (`com.amazonaws.global.cloudfront.origin-facing`); salida 443 a `0.0.0.0/0` y 5432 a `var.vpc_cidr`. Instancia: `http_tokens = "required"`, `http_put_response_hop_limit = 1`, raíz gp3 de 20 GB cifrada, `user_data_replace_on_change = true`, sin `key_name`. `user_data` = cabecera generada con `export` de variables no secretas (región, ruta de parámetros, ARN del secreto, host/puerto/nombre de la BD, bucket, repositorio, ref) seguida de `file("${path.module}/files/bootstrap.sh")`.

- [ ] **Step 5: Escribir `files/bootstrap.sh`** (`#!/usr/bin/env bash`, `set -euo pipefail`, sin interpolación de Terraform). Hace: espera hasta 5 minutos a tener salida a internet (la IP elástica se asocia después de que la instancia arranca); `dnf install` de python3.12, nginx y git; clona `REPO_URL` en `APP_GIT_REF` a `/opt/rutalibre`; crea un venv por servicio (backend + `gunicorn`, optimizador + `uvicorn`); escribe `/usr/local/bin/rutalibre-env`, que genera `/etc/rutalibre/env` (modo 600): **cada** parámetro bajo `CONFIG_PARAMETER_PATH` se vuelve una variable con su mismo nombre (así el operador añade `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY` y `ALLOWED_HOSTS` sin tocar Terraform), más `DATABASE_URL` armada con el secreto de RDS, `OPTIMIZER_URL=http://127.0.0.1:8001`, `S3_BUCKET` y `S3_REGION`; unidades systemd `rutalibre-api` (gunicorn `config.wsgi` en `127.0.0.1:8000`) y `rutalibre-optimizer` (uvicorn `app.main:app` en `127.0.0.1:8001`) con `ExecStartPre=/usr/local/bin/rutalibre-env`; nginx: `/api/`, `/admin/`, `/static/` → 8000; `/docs`, `/openapi.json` → 8001; lo demás 404. Primera línea de comentario: el script nunca se ha ejecutado en una instancia real.
  Run: `bash -n infra/terraform/modules/compute/files/bootstrap.sh` → sin salida.

- [ ] **Step 6:** Conectar `module.compute` y `module.database` en la raíz. Run: `terraform fmt -check -recursive && terraform validate && terraform test && tflint --recursive --config "$(pwd)/.tflint.hcl"` → verde.

- [ ] **Step 7: Prueba de mutación.** Añadir `"s3:*"` a la política → FALLA. Revertir. Poner `http_tokens = "optional"` → FALLA. Revertir. Añadir una segunda regla de entrada para el puerto 22 con `cidr_ipv4 = "0.0.0.0/0"`: si ningún test falla, declarar las reglas de entrada con `for_each` sobre un mapa local y afirmar que tiene exactamente una entrada. Revertir.
  Run: `grep -rnE "key_name|aws_key_pair" infra/terraform/modules` → sin coincidencias.

- [ ] **Step 8: Añadir al job `infra`** el paso `shellcheck modules/compute/files/bootstrap.sh` (shellcheck viene instalado en `ubuntu-latest`).

- [ ] **Step 9: Commit y push; job en verde.** `feat(infra): EC2 app server with least-privilege instance role`

---

### Task 5: Módulo `edge` (CloudFront) y plan del conjunto

**Files:**
- Create: `infra/terraform/modules/edge/{main,variables,outputs,versions}.tf`, `infra/terraform/tests/{edge,stack}.tftest.hcl`
- Modify: `infra/terraform/{main,outputs}.tf`

**Interfaces:**
- Consumes: `module.storage.{frontend_bucket_id,frontend_bucket_arn,frontend_bucket_regional_domain_name}`; `module.compute.public_dns`.
- Produces — módulo `edge`:
  - variables: `name_prefix`, `frontend_bucket_id`, `frontend_bucket_arn`, `frontend_bucket_regional_domain_name`, `api_origin_domain_name`, `api_path_patterns` (por defecto `["/api/*", "/admin/*", "/static/*", "/docs", "/openapi.json"]`)
  - recursos: `aws_cloudfront_distribution.this`, `aws_cloudfront_origin_access_control.frontend`, `aws_s3_bucket_policy.frontend`
  - `origin_id` fijos: `"frontend-s3"` y `"api-ec2"`
  - outputs: `domain_name`, `distribution_id`
- Produces — raíz, outputs finales: `app_url` (`"https://${module.edge.domain_name}"`), `evidence_bucket_name`, `frontend_bucket_name`, `database_address`, `instance_id`.

- [ ] **Step 1: Tests que fallan.**
  `tests/edge.tftest.hcl`, `run "https_everywhere"` con valores de prueba (`api_origin_domain_name = "ec2-test.compute-1.amazonaws.com"`, `frontend_bucket_arn = "arn:aws:s3:::fe-test"`). Aserciones sobre `aws_cloudfront_distribution.this`:
  - `enabled == true`, `default_root_object == "index.html"`, `price_class == "PriceClass_100"`;
  - `default_cache_behavior[0].target_origin_id == "frontend-s3"` y `viewer_protocol_policy == "redirect-to-https"`;
  - `length(ordered_cache_behavior) == 5`; todas con `target_origin_id == "api-ec2"` y `viewer_protocol_policy == "redirect-to-https"`; `toset(ordered_cache_behavior[*].path_pattern)` igual al conjunto por defecto;
  - el origen `"api-ec2"` tiene `custom_origin_config[0].origin_protocol_policy == "http-only"` y `domain_name == "ec2-test.compute-1.amazonaws.com"`;
  - la política `aws_s3_bucket_policy.frontend` tiene una sola sentencia `Allow`, `Action == "s3:GetObject"`, `Principal.Service == "cloudfront.amazonaws.com"`, `Resource == "arn:aws:s3:::fe-test/*"`.
  `tests/stack.tftest.hcl`: `mock_provider "aws" {}` y `run "whole_stack_plans"` con `command = plan`, **sin** bloque `module` (prueba la raíz con los valores por defecto). Aserciones: `output.evidence_bucket_name == "rutalibre-evidencias"` y `output.frontend_bucket_name == "rutalibre-frontend"`.

- [ ] **Step 2:** Run `terraform test` → FALLAN `edge` y `stack`.

- [ ] **Step 3: Implementar `modules/edge`.** Políticas administradas por nombre con `data "aws_cloudfront_cache_policy"` (`Managed-CachingOptimized`, `Managed-CachingDisabled`) y `data "aws_cloudfront_origin_request_policy"` (`Managed-AllViewer`, para que Django reciba el `Host` de CloudFront). Comportamiento por defecto: `GET`, `HEAD`. Comportamientos de API con `dynamic "ordered_cache_behavior"` sobre `var.api_path_patterns`, los 7 métodos, sin caché. OAC `sigv4`, `always`. Certificado por defecto de CloudFront; sin restricción geográfica. Política del bucket: `Condition.StringEquals["AWS:SourceArn"] = aws_cloudfront_distribution.this.arn`.
  Nota: como `AWS:SourceArn` se conoce solo tras aplicar, la política completa es desconocida durante el plan. Si las aserciones de la política no pueden evaluarse, declarar `mock_resource "aws_cloudfront_distribution"` con `defaults = { arn = "arn:aws:cloudfront::123456789012:distribution/TEST" }` y `override_during = plan` **solo en `edge.tftest.hcl`**.

- [ ] **Step 4:** Conectar `module.edge` y escribir los outputs finales de la raíz. Run: `terraform fmt -check -recursive && terraform validate && terraform test && tflint --recursive --config "$(pwd)/.tflint.hcl"` → verde, `6 passed` o más, `0 failed`.

- [ ] **Step 5: Prueba de mutación.** `viewer_protocol_policy = "allow-all"` en el comportamiento por defecto → FALLA. Revertir. Quitar `"/admin/*"` de `api_path_patterns` → FALLA. Revertir.
  Límite conocido (va a `infra/README.md` en la Tarea 6): los tests no ven el cableado entre módulos cuando el valor es un identificador calculado. Si la raíz pasara las subredes públicas a `database`, ningún test fallaría.

- [ ] **Step 6: Commit y push; job en verde.** `feat(infra): CloudFront entry point and full-stack plan test`

---

### Task 6: Checkov y documentación

**Files:**
- Modify: `.github/workflows/ci.yml`, archivos `.tf` que reciban correcciones o excepciones
- Create: `infra/README.md`, `docs/adr/0005-terraform-validado-sin-aplicar.md`
- Modify: `README.md`, `docs/architecture.md`, `docs/EXPLICACION.md`

**Interfaces:**
- Consumes: todo lo anterior. No produce interfaces nuevas.

- [ ] **Step 1: Ejecutar Checkov y guardar la lista inicial.**
  Run: `.tools/checkov-venv/Scripts/checkov -d infra/terraform --framework terraform --compact --quiet`
  Expected: una lista de hallazgos `FAILED` (es el "test que falla" de esta tarea).

- [ ] **Step 2: Resolver cada hallazgo con esta regla.** Si se corrige sin costo mensual y sin añadir un servicio nuevo → corregir en el `.tf` (y añadir la aserción al test del módulo si es una propiedad de seguridad). Si no → `#checkov:skip=<ID>:<razón en inglés, una línea>` sobre el recurso. Excepciones esperadas (los ID exactos salen del paso 1): Multi-AZ y monitoreo detallado de RDS, monitoreo detallado de EC2, WAF y registros de acceso de CloudFront, política de cabeceras y certificado propio de CloudFront, origen HTTP entre CloudFront y EC2 (exigiría balanceador y certificado), registros de acceso y replicación entre regiones de S3, notificaciones de eventos de S3, claves KMS propias, registros de flujo de la VPC, EC2 con IP pública.
  Run: el mismo comando → `Failed checks: 0`; `terraform test` sigue en verde.

- [ ] **Step 3: Añadir al job `infra`** los pasos `actions/setup-python@v5` (3.12), `pip install checkov==3.4.5` y `checkov -d . --framework terraform --compact --quiet`.

- [ ] **Step 4: Escribir `infra/README.md`** (español) con estas secciones: Qué es (validado, **no aplicado**); Diagrama (el mermaid de la spec); Módulos (una línea cada uno); Cómo validarlo en local (los 6 comandos); Qué fijan los tests (tabla de la spec, actualizada); Qué **no** está validado (el proveedor es simulado; `bootstrap.sh` nunca corrió; el cableado entre módulos por identificadores calculados no se prueba; el origen CORS del bucket y `ALLOWED_HOSTS` necesitan el dominio de CloudFront, que solo existe tras un primer `apply`, así que harían falta dos pasadas); Qué faltaría para aplicarlo (los 5 puntos de la spec más crear los parámetros en Parameter Store); Costo estimado (tabla por servicio verificada en la calculadora de precios de AWS el día de la implementación, con la fecha; advertir que `apply` genera cobros); Excepciones de Checkov (tabla: ID, recurso, razón).

- [ ] **Step 5: Actualizar `README.md`.**
  - Fila "AWS: EC2, RDS": `Terraform en [infra/terraform/](infra/terraform/): VPC, EC2, RDS, S3, IAM y CloudFront. Validado en el CI (formato, esquema, TFLint, N tests con proveedor simulado, Checkov); **no aplicado**: el demo corre en Vercel.` con N = número real de bloques `run`.
  - Fila "Revisión de código y CI": añadir el job de infraestructura.
  - "Camino a AWS": la política IAM pasa a ser la de `iam.tf` (6 acciones, incluye `s3:ListBucketVersions` y `s3:DeleteObjectVersion`); la última línea enlaza a `infra/README.md` en lugar de prometer la fase B.
  - Hoja de ruta: Fase B tachada, "Hecha (validada, no aplicada)".

- [ ] **Step 6: Documentación técnica.**
  - `docs/architecture.md`: sección "Infraestructura como código (AWS)" con los módulos, las cuatro decisiones de seguridad (BD privada, sin SSH, IAM mínimo, secretos fuera de Terraform) y cómo se verifica.
  - `docs/adr/0005-terraform-validado-sin-aplicar.md`: mismo formato que el 0004 (Contexto, Decisión, Consecuencias, Alternativas descartadas: LocalStack, cuenta AWS con créditos, solo documentar).
  - `docs/EXPLICACION.md`: sección "9. Infraestructura como código con Terraform": qué es el estado, qué hace `plan` frente a `apply`, por qué un proveedor simulado, cómo leer un `.tftest.hcl`, por qué la BD va en subred privada, qué es un rol de instancia; 5 preguntas de estudio con el mismo estilo de las secciones 1–8.

- [ ] **Step 7: Verificación final completa.**
  Run (en `infra/terraform`): `terraform fmt -check -recursive && terraform validate && tflint --recursive --config "$(pwd)/.tflint.hcl" && terraform test` y Checkov → todo en verde.
  Run: `git status --short` → ningún `.tfstate`, `.terraform/` ni archivo fuera de `infra/`, `docs/`, `README.md`, `.gitignore`, `.github/`.
  Run: `grep -rniE "password\s*=|secret_key\s*=|AKIA" infra/` → sin coincidencias.

- [ ] **Step 8: Commit y push; los 5 jobs en verde.** `feat(infra): Checkov in CI and documentation for the AWS design`
  Comprobar que las tres URL de producción siguen respondiendo (el push redepliega Vercel aunque no cambie código de la aplicación).
