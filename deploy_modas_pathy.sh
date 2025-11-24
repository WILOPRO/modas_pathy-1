#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "❌ Ejecuta con sudo: sudo ./deploy_modas_pathy.sh"
  exit 1
fi

echo "=============================================="
echo "  DEPLOY MODAS PATHY — Ubuntu 20.04"
echo "=============================================="

read -rp "Dominio principal (ej: modaspathy.com): " DOMAIN
DOMAIN="${DOMAIN:-example.com}"

read -rp "Subdominio (vacío si no usar, ej: tienda): " SUBDOMAIN
if [[ -n "$SUBDOMAIN" ]]; then
  FQDN="${SUBDOMAIN}.${DOMAIN}"
else
  FQDN="${DOMAIN}"
fi

read -rp "Ruta del proyecto [/var/www/modas_pathy]: " APP_DIR
APP_DIR="${APP_DIR:-/var/www/modas_pathy}"

read -rp "Archivo/módulo Flask sin .py [app]: " MODULE
MODULE="${MODULE:-app}"

read -rp "Variable Flask dentro del módulo [app]: " FLASK_VAR
FLASK_VAR="${FLASK_VAR:-app}"

read -rp "Usuario que ejecutará Gunicorn [www-data]: " APP_USER
APP_USER="${APP_USER:-www-data}"

read -rp "¿Modo de bind? (socket recomendado / port opcional) [socket/port]: " BIND_MODE
BIND_MODE="${BIND_MODE:-socket}"

PORT="8000"
if [[ "$BIND_MODE" == "port" ]]; then
  read -rp "Puerto interno Gunicorn [8000]: " PORT
  PORT="${PORT:-8000}"
  GUNICORN_BIND="0.0.0.0:${PORT}"
else
  GUNICORN_BIND="unix:/run/modas_pathy.sock"
fi

read -rp "SECRET_KEY (enter para generar automáticamente): " SECRET_KEY
if [[ -z "$SECRET_KEY" ]]; then
  SECRET_KEY="$(openssl rand -hex 32)"
  echo "✅ SECRET_KEY generada: $SECRET_KEY"
fi

read -rp "¿Crear superadmin ahora? [s/N]: " CREATE_ADMIN
CREATE_ADMIN="${CREATE_ADMIN,,}"

ADMIN_USERNAME=""
ADMIN_NAME=""
ADMIN_PASSWORD=""

if [[ "$CREATE_ADMIN" == "s" || "$CREATE_ADMIN" == "si" ]]; then
  read -rp "Username superadmin: " ADMIN_USERNAME
  read -rp "Nombre superadmin: " ADMIN_NAME
  read -rsp "Password superadmin: " ADMIN_PASSWORD
  echo ""
fi

read -rp "¿Habilitar SSL (Let's Encrypt) ahora? [s/N]: " ENABLE_SSL
ENABLE_SSL="${ENABLE_SSL,,}"

echo ""
echo "🚀 Instalando dependencias del sistema..."
apt update -y
apt install -y python3 python3-venv python3-pip nginx ufw \
               build-essential libssl-dev libffi-dev

echo "✅ Preparando carpeta del proyecto..."
mkdir -p "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "🐍 Creando entorno virtual..."
cd "$APP_DIR"

if [[ ! -d "venv" ]]; then
  sudo -u "$APP_USER" python3 -m venv venv
fi

echo "📦 Instalando dependencias Python..."
sudo -u "$APP_USER" bash -c "source venv/bin/activate && pip install --upgrade pip"
sudo -u "$APP_USER" bash -c "source venv/bin/activate && pip install -r requirements.txt"
sudo -u "$APP_USER" bash -c "source venv/bin/activate && pip install gunicorn"

echo "🔐 Creando archivo de entorno /etc/modas_pathy.env ..."
cat > /etc/modas_pathy.env <<EOF
SECRET_KEY=$SECRET_KEY
FLASK_ENV=production
EOF
chmod 640 /etc/modas_pathy.env
chown root:"$APP_USER" /etc/modas_pathy.env

echo "🧩 Creando servicio systemd..."
cat > /etc/systemd/system/modas_pathy.service <<EOF
[Unit]
Description=Gunicorn for Modas Pathy
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=/etc/modas_pathy.env
Environment="PATH=$APP_DIR/venv/bin"

EOF

if [[ "$BIND_MODE" == "socket" ]]; then
  cat >> /etc/systemd/system/modas_pathy.service <<EOF
ExecStartPre=/bin/rm -f /run/modas_pathy.sock
ExecStart=$APP_DIR/venv/bin/gunicorn -w 3 -b $GUNICORN_BIND $MODULE:$FLASK_VAR
EOF
else
  cat >> /etc/systemd/system/modas_pathy.service <<EOF
ExecStart=$APP_DIR/venv/bin/gunicorn -w 3 -b $GUNICORN_BIND $MODULE:$FLASK_VAR
EOF
fi

cat >> /etc/systemd/system/modas_pathy.service <<EOF
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "🌐 Configurando Nginx..."
PROXY_TARGET="http://unix:/run/modas_pathy.sock"
if [[ "$BIND_MODE" == "port" ]]; then
  PROXY_TARGET="http://127.0.0.1:${PORT}"
fi

cat > /etc/nginx/sites-available/modas_pathy <<EOF
server {
    listen 80;
    server_name $FQDN www.$FQDN;

    client_max_body_size 16M;

    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        include proxy_params;
        proxy_pass $PROXY_TARGET;
    }
}
EOF

ln -sf /etc/nginx/sites-available/modas_pathy /etc/nginx/sites-enabled/modas_pathy
rm -f /etc/nginx/sites-enabled/default

echo "🔐 Firewall UFW..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "♻️ Reiniciando servicios..."
systemctl daemon-reload
systemctl enable modas_pathy
systemctl restart modas_pathy

nginx -t
systemctl restart nginx

echo "✅ Deploy HTTP listo: http://$FQDN"

if [[ -n "$ADMIN_USERNAME" ]]; then
  echo "👤 Creando superadmin..."
  sudo -u "$APP_USER" bash -c "source venv/bin/activate && python3 - <<PY
import importlib
from werkzeug.security import generate_password_hash

mod = importlib.import_module('$MODULE')
app = getattr(mod, '$FLASK_VAR')
db = getattr(mod, 'db')
User = getattr(mod, 'User')

username = '$ADMIN_USERNAME'
name = '$ADMIN_NAME'
pwd = '$ADMIN_PASSWORD'

with app.app_context():
    u = User.query.filter_by(username=username).first()
    if u:
        print('⚠️ Ya existe ese usuario, no se crea otro.')
    else:
        new = User(username=username, name=name,
                   password=generate_password_hash(pwd),
                   is_superadmin=True)
        db.session.add(new)
        db.session.commit()
        print('✅ Superadmin creado con éxito.')
PY"
fi

if [[ "$ENABLE_SSL" == "s" || "$ENABLE_SSL" == "si" ]]; then
  echo "🔒 Instalando Certbot..."
  apt install -y certbot python3-certbot-nginx
  echo "🔒 Generando SSL..."
  certbot --nginx -d "$FQDN" -d "www.$FQDN"
  echo "✅ SSL activo: https://$FQDN"
fi

echo "=============================================="
echo "✅ TODO LISTO. Web publicada en: $FQDN"
echo "=============================================="
