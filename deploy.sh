#!/usr/bin/env bash
set -euo pipefail

# Variables principales
APP_NAME="modas_pathy"
APP_USER="pathy"
APP_DIR="/var/www/$APP_NAME"
REPO_URL="https://github.com/WILOPRO/modas_pathy-1.git"
DOMAIN="tienda.modaspathy.shop"
EMAIL_LETSENCRYPT="tu-correo@example.com"   # cambia esto

# Paquetes base
apt update
apt install -y git python3-venv python3-pip nginx certbot python3-certbot-nginx

# Usuario sin login para la app
id -u "$APP_USER" >/dev/null 2>&1 || adduser --system --group --home "$APP_DIR" "$APP_USER"

# Código
if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
else
  cd "$APP_DIR"
  sudo -u "$APP_USER" git pull --ff-only
fi

# Virtualenv + dependencias
cd "$APP_DIR"
sudo -u "$APP_USER" python3 -m venv venv
sudo -u "$APP_USER" bash -lc "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

# Coloca tu archivo .env antes de iniciar (no se versiona)
if [ ! -f "$APP_DIR/.env" ]; then
  echo "Crea $APP_DIR/.env con SECRET_KEY, DB, mail, etc. y vuelve a correr el script."
  exit 1
fi

# Service de systemd para Gunicorn
cat >/etc/systemd/system/$APP_NAME.service <<'EOF'
[Unit]
Description=Gunicorn for modas_pathy
After=network.target

[Service]
User=pathy
Group=www-data
WorkingDirectory=/var/www/modas_pathy
EnvironmentFile=/var/www/modas_pathy/.env
Environment="FLASK_ENV=production"
Environment="FLASK_APP=app.py"
ExecStart=/var/www/modas_pathy/venv/bin/gunicorn --workers 3 --bind unix:/var/www/modas_pathy/modas_pathy.sock "app:app"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now $APP_NAME

# Nginx (sin SSL aún)
cat >/etc/nginx/sites-available/$APP_NAME.conf <<'EOF'
server {
    listen 80;
    server_name tienda.modaspathy.shop www.tienda.modaspathy.shop;

    client_max_body_size 32M;

    location / {
        proxy_pass http://unix:/var/www/modas_pathy/modas_pathy.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/modas_pathy/static/;
        expires 30d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME.conf /etc/nginx/sites-enabled/$APP_NAME.conf
nginx -t && systemctl restart nginx

# Certificado SSL con Let's Encrypt
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" -m "$EMAIL_LETSENCRYPT" --agree-tos --redirect --non-interactive

echo "Despliegue terminado. Verifica que el servicio y Nginx estén activos."
