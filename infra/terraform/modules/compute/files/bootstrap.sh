# shellcheck shell=bash
#
# First-boot setup of the RutaLibre app server (Amazon Linux 2023).
#
# WARNING: this script has never run on a real instance. The infrastructure is
# validated in CI (fmt, validate, TFLint, tests with a mocked provider,
# Checkov, shellcheck) but never applied. See infra/README.md.
#
# Terraform prepends `export NAME="value"` lines for these non-secret values:
#   AWS_REGION CONFIG_PARAMETER_PATH DB_SECRET_ARN DB_HOST DB_PORT DB_NAME
#   S3_BUCKET REPO_URL APP_GIT_REF
# Secrets are read on the instance, at service start, by rutalibre-env.

set -euo pipefail

: "${AWS_REGION:?}" "${CONFIG_PARAMETER_PATH:?}" "${DB_SECRET_ARN:?}"
: "${DB_HOST:?}" "${DB_PORT:?}" "${DB_NAME:?}" "${S3_BUCKET:?}"
: "${REPO_URL:?}" "${APP_GIT_REF:?}"

APP_DIR=/opt/rutalibre
CONF_DIR=/etc/rutalibre

# 1. Network. The Elastic IP is attached after the instance starts, so the
#    first seconds may have no route to the internet. Wait up to 5 minutes.
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 -o /dev/null https://github.com; then
    break
  fi
  sleep 5
done

# 2. Packages. The AWS CLI comes with Amazon Linux 2023.
dnf install -y python3.12 nginx git jq

# 3. Code and one virtual environment per service.
id rutalibre >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /sbin/nologin rutalibre
git clone --depth 1 --branch "$APP_GIT_REF" "$REPO_URL" "$APP_DIR"

python3.12 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/pip" install --no-cache-dir -r "$APP_DIR/backend/requirements.txt" gunicorn
python3.12 -m venv "$APP_DIR/optimizer/.venv"
"$APP_DIR/optimizer/.venv/bin/pip" install --no-cache-dir -r "$APP_DIR/optimizer/requirements.txt" uvicorn
chown -R rutalibre:rutalibre "$APP_DIR"

# 4. Settings. The non-secret values are kept for rutalibre-env.
install -d -m 750 "$CONF_DIR"
cat > "$CONF_DIR/bootstrap.env" <<EOF
AWS_REGION=$AWS_REGION
CONFIG_PARAMETER_PATH=$CONFIG_PARAMETER_PATH
DB_SECRET_ARN=$DB_SECRET_ARN
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
S3_BUCKET=$S3_BUCKET
EOF
chmod 600 "$CONF_DIR/bootstrap.env"

# rutalibre-env writes $CONF_DIR/env (mode 600) on every boot:
# - every parameter under CONFIG_PARAMETER_PATH becomes a variable with the
#   same name (DJANGO_SECRET_KEY, JWT_SIGNING_KEY, ALLOWED_HOSTS, ...);
# - DATABASE_URL is built from the secret RDS manages.
cat > /usr/local/bin/rutalibre-env <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=/dev/null
source /etc/rutalibre/bootstrap.env

out=$(mktemp /etc/rutalibre/env.XXXXXX)
chmod 600 "$out"

aws ssm get-parameters-by-path \
  --region "$AWS_REGION" --path "$CONFIG_PARAMETER_PATH" \
  --recursive --with-decryption \
  --query 'Parameters[].[Name,Value]' --output json \
  | jq -r '.[] | "\(.[0] | split("/") | last)=\(.[1])"' >> "$out"

secret=$(aws secretsmanager get-secret-value \
  --region "$AWS_REGION" --secret-id "$DB_SECRET_ARN" \
  --query SecretString --output text)
db_user=$(jq -r '.username | @uri' <<<"$secret")
db_password=$(jq -r '.password | @uri' <<<"$secret")

{
  echo "DATABASE_URL=postgres://${db_user}:${db_password}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require"
  echo "OPTIMIZER_URL=http://127.0.0.1:8001"
  echo "S3_BUCKET=${S3_BUCKET}"
  echo "S3_REGION=${AWS_REGION}"
} >> "$out"

mv "$out" /etc/rutalibre/env
SCRIPT
chmod 750 /usr/local/bin/rutalibre-env

# rutalibre-refresh runs every 5 minutes. RDS rotates the master password
# (every 7 days by default) and Django reconnects on every request, so the
# services are restarted as soon as the settings change.
cat > /usr/local/bin/rutalibre-refresh <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
before=$(sha256sum /etc/rutalibre/env 2>/dev/null || true)
/usr/local/bin/rutalibre-env
after=$(sha256sum /etc/rutalibre/env)
if [ "$before" != "$after" ]; then
  systemctl try-restart rutalibre-api.service rutalibre-optimizer.service
fi
SCRIPT
chmod 750 /usr/local/bin/rutalibre-refresh

# 5. Services. Both listen only on 127.0.0.1; nginx is the only way in.
cat > /etc/systemd/system/rutalibre-env.service <<'EOF'
[Unit]
Description=RutaLibre settings from Parameter Store and Secrets Manager
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/rutalibre-env
EOF

cat > /etc/systemd/system/rutalibre-refresh.service <<'EOF'
[Unit]
Description=Refresh RutaLibre settings (rotated database password)

[Service]
Type=oneshot
ExecStart=/usr/local/bin/rutalibre-refresh
EOF

cat > /etc/systemd/system/rutalibre-env.timer <<'EOF'
[Unit]
Description=Refresh RutaLibre settings every 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
Unit=rutalibre-refresh.service

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/rutalibre-api.service <<EOF
[Unit]
Description=RutaLibre API (Django + gunicorn)
Requires=rutalibre-env.service
After=rutalibre-env.service

[Service]
User=rutalibre
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$CONF_DIR/env
ExecStartPre=$APP_DIR/backend/.venv/bin/python manage.py migrate --noinput
ExecStartPre=$APP_DIR/backend/.venv/bin/python manage.py collectstatic --noinput
ExecStart=$APP_DIR/backend/.venv/bin/gunicorn config.wsgi --bind 127.0.0.1:8000 --workers 2
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/rutalibre-optimizer.service <<EOF
[Unit]
Description=RutaLibre optimizer (FastAPI + uvicorn)
Requires=rutalibre-env.service
After=rutalibre-env.service

[Service]
User=rutalibre
WorkingDirectory=$APP_DIR/optimizer
EnvironmentFile=$CONF_DIR/env
ExecStart=$APP_DIR/optimizer/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 6. nginx. CloudFront sends its own host name (*.cloudfront.net). Only the
#    API, the admin, Django static files and the optimizer docs are exposed;
#    /optimize stays private (Django calls it on 127.0.0.1).
cat > /etc/nginx/conf.d/rutalibre.conf <<'EOF'
server {
    listen 80;
    server_name .cloudfront.net;
    client_max_body_size 1m;

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;

    location /api/    { proxy_pass http://127.0.0.1:8000; }
    location /admin/  { proxy_pass http://127.0.0.1:8000; }
    location /static/ { proxy_pass http://127.0.0.1:8000; }

    location = /docs         { proxy_pass http://127.0.0.1:8001; }
    location = /openapi.json { proxy_pass http://127.0.0.1:8001; }

    location / { return 404; }
}
EOF

systemctl daemon-reload
systemctl enable --now rutalibre-api.service rutalibre-optimizer.service nginx.service rutalibre-env.timer
