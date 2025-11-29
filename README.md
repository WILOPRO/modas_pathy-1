# Modas Pathy - Sistema de Tienda Virtual

Sistema completo de tienda virtual con integración de WhatsApp y PayPal para la venta de productos de moda.

## 🚀 Características Principales

### Tienda Pública
- **Página de Inicio**: Hero section, productos destacados, novedades y tendencias
- **Catálogo**: Filtros por categoría, búsqueda y ordenamiento con paginación
- **Detalle de Producto**: Galería de imágenes, información completa, botones de compra
- **Compra por WhatsApp**: Modal de confirmación con envío directo al WhatsApp de la tienda
- **Compra con PayPal**: Integración completa con PayPal SDK
- **Rastreo de Pedidos**: Sistema público para ver estado del pedido

### Panel de Administración
- **Dashboard**: Estadísticas de productos, pedidos y visitas
- **Gestión de Pedidos**: Lista, detalle, cambio de estado con historial
- **Gestión de Productos**: CRUD completo con múltiples imágenes
- **Gestión de Categorías**: CRUD con iconos personalizables
- **Temas Personalizables**: Colores de la tienda modificables
- **Información de Contacto**: Redes sociales y datos de contacto
- **Gestión de Usuarios**: Control de acceso al panel admin

## 📦 Instalación

### Requisitos
- Python 3.8+
- pip

### Pasos

1. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

2. **Ejecutar la aplicación**:
```bash
python app.py
```

3. **Acceder a la tienda**:
- Tienda pública: http://localhost:5000
- Panel admin: http://localhost:5000/admin

### Credenciales por defecto
- **Usuario**: admin
- **Contraseña**: admin123

## 📁 Estructura del Proyecto

```
modas_pathy/
├── app.py              # Aplicación principal Flask
├── config.py           # Configuración (PayPal, BD, etc.)
├── requirements.txt    # Dependencias Python
├── static/
│   ├── css/
│   │   ├── styles.css     # Estilos públicos
│   │   └── admin.css      # Estilos admin
│   ├── uploads/           # Imágenes de productos
│   ├── perfiles/          # Fotos de perfil
│   └── images/            # Logo, favicon, etc.
└── templates/
    ├── public/            # Templates públicos
    │   ├── base.html
    │   ├── index.html
    │   ├── catalogo.html
    │   ├── producto_detalle.html
    │   ├── order_confirmation.html
    │   └── track_order.html
    ├── admin/             # Templates admin
    │   ├── base_admin.html
    │   ├── dashboard.html
    │   ├── pedidos.html
    │   ├── pedido_detalle.html
    │   ├── productos.html
    │   ├── categorias.html
    │   ├── perfil.html
    │   └── login.html
    └── errors/            # Templates de error
        ├── 404.html
        ├── 403.html
        └── 500.html
```

## 💳 Configuración de PayPal

El proyecto usa PayPal Sandbox por defecto. Para producción:

1. Editar `config.py`:
```python
PAYPAL_CLIENT_ID = 'tu_client_id_live'
PAYPAL_MODE = 'live'
```

2. Obtener credenciales en: https://developer.paypal.com

## 📱 Configuración de WhatsApp

1. Acceder al panel admin → Contacto
2. Ingresar número de WhatsApp con código de país (ej: +591 71234567)

## 🎨 Personalización de Temas

1. Panel admin → Temas
2. Crear nuevo tema con colores personalizados
3. Activar el tema deseado

## 📊 Sistema de Pedidos

### Estados disponibles:
1. **Recibido**: Pedido registrado en el sistema
2. **Pagado**: Pago confirmado (automático con PayPal)
3. **Confeccionando**: En proceso de elaboración
4. **Preparando envío**: Listo para enviar
5. **En camino**: En tránsito al cliente
6. **Entregado**: Pedido completado

### Códigos de pedido:
- Formato: `MP-YYYY-#####`
- Ejemplo: `MP-2025-00001`

## 🔒 Seguridad

- Contraseñas hasheadas con Werkzeug
- Protección CSRF en formularios
- Sesiones seguras con Flask-Login

## 📝 Licencia

Proyecto privado - Modas Pathy © 2025
