#!/bin/bash
set -e

echo "======================================="
echo " INSTALANDO MODAS PATHY (Automático) "
echo "======================================="

PROJECT_DIR="/var/www/modas_pathy"
REPO_URL="https://github.com/WILOPRO/modas_pathy-1.git"
DOMAIN="tienda.modaspathy.shop"
ADMIN_USER="superadmin"
ADMIN_PASS="123456"
ADMIN_NAME="Administrador Pathy"

echo ">>> Actualizando servidor..."
apt update -y && apt upgrade -y

echo ">>> Instalando dependencias esenciales..."
apt install -y python3 python3-venv python3-pip nginx git curl

echo ">>> Eliminando instalación previa..."
rm -rf $PROJECT_DIR
mkdir -p $PROJECT_DIR

echo ">>> Clonando repositorio..."
git clone $REPO_URL $PROJECT_DIR

echo ">>> Entrando al proyecto..."
cd $PROJECT_DIR

echo ">>> Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

echo ">>> Instalando requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo ">>> Creando Base de Datos limpia..."
rm -f modas_pathy.db
python3 - <<END
from app import db, User
db.create_all()
u = User(username="$ADMIN_USER", name="$ADMIN_NAME")
u.set_password("$ADMIN_PASS")
u.is_superadmin = True
db.session.add(u)
db.session.commit()
END

echo ">>> Corrigiendo columnas necesarias (products)..."
cat > fix_products.py <<EOF
import sqlite3

DB = "modas_pathy.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

def add_column(table, column, coltype):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        print("ADDED:", column)
    except sqlite3.OperationalError:
        print("EXISTS:", column)

add_column("products", "views", "INTEGER DEFAULT 0")
add_column("products", "updated_at", "TEXT")
add_column("products", "is_new", "INTEGER DEFAULT 0")
add_column("products", "is_trending", "INTEGER DEFAULT 0")
add_column("products", "is_featured", "INTEGER DEFAULT 0")
add_column("products", "stock", "INTEGER DEFAULT 0")
add_column("products", "custom_measurements", "TEXT")

conn.commit()
conn.close()
EOF

python3 fix_products.py

echo ">>> Creando servicio Gunicorn..."
cat > /etc/systemd/system/modas_pathy.service <<EOF
[Unit]
Description=Gunicorn for Modas Pathy
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/modas_pathy.sock app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable modas_pathy
systemctl restart modas_pathy

echo ">>> Configurando NGINX..."
cat > /etc/nginx/sites-available/$DOMAIN <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/modas_pathy.sock;
    }

    location /static/ {
        alias $PROJECT_DIR/static/;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl restart nginx

echo ">>> Instalando CERTBOT SSL..."
apt install -y certbot python3-certbot-nginx

certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m wilberchoqueyucra@gmail.com

echo ">>> Habilitando firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
echo "y" | ufw enable

echo "======================================="
echo " INSTALLACIÓN COMPLETADA EXITOSAMENTE "
echo "======================================="
echo " Panel Admin → https://$DOMAIN/admin/login"
echo " Usuario: $ADMIN_USER"
echo " Clave: $ADMIN_PASS"
echo "======================================="
