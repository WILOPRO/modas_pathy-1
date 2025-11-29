"""
Modas Pathy - Tienda Virtual
Versión 2.0 - Código refactorizado y optimizado
"""

import os
import re
import random
import requests
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for, flash,
    request, abort, Response, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, MultipleFileField, FileField
from wtforms import (
    StringField, PasswordField, SubmitField, FloatField,
    TextAreaField, SelectField, BooleanField, DateField, HiddenField
)
from wtforms.validators import (
    DataRequired, InputRequired, Length, Optional, EqualTo, Regexp, NumberRange
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from sqlalchemy import or_, JSON
from sqlalchemy.orm.attributes import flag_modified

from config import config

# ═══════════════════════════════════════════════════════════════════════════
#                           INICIALIZACIÓN
# ═══════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.config.from_object(config['development'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = 'Por favor, inicia sesión para acceder.'
login_manager.login_message_category = 'info'

# Crear carpetas necesarias
UPLOAD_FOLDER = app.config.get('UPLOAD_FOLDER', os.path.join('static', 'uploads'))
PROFILE_FOLDER = app.config.get('PROFILE_FOLDER', os.path.join('static', 'perfiles'))
QR_FOLDER = app.config.get('QR_FOLDER', os.path.join('static', 'qr'))
CUSTOM_ORDER_FOLDER = app.config.get('CUSTOM_ORDER_FOLDER', os.path.join('static', 'custom_orders'))
ALLOWED_EXTENSIONS = app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})

for folder in (UPLOAD_FOLDER, PROFILE_FOLDER, QR_FOLDER, CUSTOM_ORDER_FOLDER):
    os.makedirs(folder, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
#                              MODELOS
# ═══════════════════════════════════════════════════════════════════════════

class User(UserMixin, db.Model):
    """Modelo de usuario/administrador"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128))
    password = db.Column(db.String(256), nullable=False)
    is_superadmin = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    """Modelo de categoría de productos"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(256))
    icon = db.Column(db.String(50), default='bi-tag')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    products = db.relationship('Product', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    """Modelo de producto"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    slug = db.Column(db.String(150))
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)  # Para mostrar descuentos
    stock = db.Column(db.Integer, default=0)
    sku = db.Column(db.String(50))
    is_on_sale = db.Column(db.Boolean, default=False)
    promo_text = db.Column(db.String(80))
    
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    
    is_active = db.Column(db.Boolean, default=True)
    is_new = db.Column(db.Boolean, default=False)
    is_trending = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    images = db.relationship('ProductImage', backref='product', lazy='dynamic',
                            cascade='all, delete-orphan')
    orders = db.relationship('Order', back_populates='product', cascade='all, delete-orphan')
    
    @property
    def main_image(self):
        """Obtiene la imagen principal del producto"""
        img = self.images.filter_by(is_main=True).first()
        if not img:
            img = self.images.first()
        return img
    
    @property
    def has_discount(self):
        """Verifica si el producto tiene descuento"""
        return bool(self.is_on_sale and self.original_price and self.original_price > self.price)
    
    @property
    def discount_percent(self):
        """Calcula el porcentaje de descuento"""
        if self.has_discount:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0
    
    @property
    def promo_label(self):
        """Texto de badge promocional"""
        return (self.promo_text or '').strip() or 'Oferta'
    
    def __repr__(self):
        return f'<Product {self.name}>'


class ProductImage(db.Model):
    """Modelo de imagen de producto"""
    __tablename__ = 'product_images'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    is_main = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProductImage {self.filename}>'


class Order(db.Model):
    """Modelo de pedidos"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(512))
    payment_method = db.Column(db.String(20), nullable=False)  # whatsapp / paypal / qr
    total = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(50), default='Recibido')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(128))
    customer_phone = db.Column(db.String(32))
    history = db.Column(JSON, default=list)
    order_notes = db.Column(db.Text)
    
    product = db.relationship('Product', back_populates='orders')
    
    def __repr__(self):
        return f'<Order {self.order_code}>'


class Client(db.Model):
    """Cliente para pedidos personalizados"""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(32), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    measurements = db.Column(JSON, default=dict)  # Medidas por tipo de prenda
    
    custom_orders = db.relationship('CustomOrder', back_populates='client', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Client {self.name}>'


class CustomOrder(db.Model):
    """Pedido personalizado (sastreria)"""
    __tablename__ = 'custom_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    garment_type = db.Column(db.String(40), nullable=False)
    delivery_date = db.Column(db.Date)
    deposit = db.Column(db.Float)
    total = db.Column(db.Float, nullable=False, default=0)
    observations = db.Column(db.Text)
    is_urgent = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(30), default='pendiente')
    measurements = db.Column(JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', back_populates='custom_orders')
    images = db.relationship('CustomOrderImage', backref='order', cascade='all, delete-orphan', lazy='dynamic')
    items = db.relationship('CustomOrderItem', backref='order', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f'<CustomOrder {self.code}>'


class CustomOrderImage(db.Model):
    """Imagenes asociadas a pedidos personalizados"""
    __tablename__ = 'custom_order_images'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('custom_orders.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CustomOrderItem(db.Model):
    """Prendas asociadas a un pedido personalizado"""
    __tablename__ = 'custom_order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('custom_orders.id'), nullable=False, index=True)
    garment_type = db.Column(db.String(40), nullable=False)
    measurements = db.Column(JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Theme(db.Model):
    """Modelo de tema visual"""
    __tablename__ = 'themes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    primary = db.Column(db.String(7), nullable=False, default='#8F2D56')
    secondary = db.Column(db.String(7), nullable=False, default='#E36485')
    accent = db.Column(db.String(7), nullable=False, default='#25D366')
    text_color = db.Column(db.String(7), nullable=False, default='#333333')
    bg_color = db.Column(db.String(7), nullable=False, default='#F8F9FA')
    success = db.Column(db.String(7), nullable=False, default='#2A9D8F')
    error = db.Column(db.String(7), nullable=False, default='#E63946')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Theme {self.name}>'


class ContactInfo(db.Model):
    """Información de contacto de la tienda"""
    __tablename__ = 'contact_info'
    
    id = db.Column(db.Integer, primary_key=True)
    whatsapp = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(128))
    tiktok = db.Column(db.String(128))
    facebook = db.Column(db.String(256))
    instagram = db.Column(db.String(128))
    youtube = db.Column(db.String(256))
    telegram = db.Column(db.String(128))
    address = db.Column(db.String(256))
    city = db.Column(db.String(100))
    schedule = db.Column(db.String(256))
    map_embed = db.Column(db.Text)  # Para embed de Google Maps


class Notification(db.Model):
    """Notificaciones del sistema"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(256), nullable=False)
    type = db.Column(db.String(20), default='info')  # info, success, warning, danger
    admin_name = db.Column(db.String(128), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<Notification {self.message[:30]}>'


class SiteSettings(db.Model):
    """Configuración general del sitio"""
    __tablename__ = 'site_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), default='Modas Pathy')
    tagline = db.Column(db.String(200), default='Elegancia de la cholita boliviana')
    logo = db.Column(db.String(256))
    favicon = db.Column(db.String(256))
    meta_description = db.Column(db.String(300))
    meta_keywords = db.Column(db.String(300))
    show_prices = db.Column(db.Boolean, default=True)
    maintenance_mode = db.Column(db.Boolean, default=False)
    exchange_rate = db.Column(db.Float, default=6.96)
    qr_image = db.Column(db.String(256))
# -------------------------------------------------
#                            FORMULARIOS
# -------------------------------------------------

ORDER_STATUSES = [
    'Pagado',
    'Recibido',
    'Confeccionando',
    'Preparando envio',
    'En camino',
    'Entregado'
]

CUSTOM_ORDER_TYPES = [
    'Blusa Cochala',
    'Blusa Sucrena',
    'Pollera Cochala',
    'Pollera Sucrena',
    'Centro Cochala',
    'Centro Sucrena'
]

CUSTOM_ORDER_STATUSES = [
    'pendiente',
    'diseno',
    'corte',
    'confeccion',
    'prueba',
    'ajustes',
    'listo',
    'entregado',
    'en proceso'  # Compatibilidad con estados anteriores
]

CUSTOM_ORDER_STATUS_LABELS = {
    'pendiente': 'Pendiente',
    'diseno': 'En diseño',
    'corte': 'En corte',
    'confeccion': 'En confección',
    'prueba': 'En prueba',
    'ajustes': 'Ajustes',
    'listo': 'Listo',
    'entregado': 'Entregado',
    'en proceso': 'En proceso'
}

# Campos de medidas por tipo
GARMENT_FIELDS = {
    'Blusa Cochala': ['largo_espalda','largo_delantero','cintura','busto','media_cintura','sisa','escote','largo_manga','puno','cuello','abertura','ancho_espalda','figura'],
    'Blusa Sucrena': ['largo_espalda','largo_delantero','cintura','busto','media_cintura','sisa','escote','largo_manga','puno','cuello','abertura','ancho_espalda','figura'],
    'Pollera Cochala': ['cintura','alforza','panos','wato','corridas','color'],
    'Pollera Sucrena': ['cintura','cadera','talla','panos','quebrado','wato','color','figura'],
    'Centro Cochala': ['cintura','talla'],
    'Centro Sucrena': ['cintura','cadera','quebrado','talla']
}

HEX_COLOR = Regexp(r'^#(?:[0-9a-fA-F]{3}){1,2}$', message='Debe ser un color hex valido')

class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(message='El usuario es requerido')])
    password = PasswordField('Contrasena', validators=[DataRequired(message='La contrasena es requerida')])
    remember = BooleanField('Recordarme')
    submit = SubmitField('Ingresar')

class CategoryForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=64)])
    description = TextAreaField('Descripcion', validators=[Optional(), Length(max=256)])
    icon = StringField('Icono (Bootstrap Icons)', validators=[Optional(), Length(max=50)])
    is_active = BooleanField('Activa', default=True)
    submit = SubmitField('Guardar')

class ProductForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Descripcion', validators=[Optional()])
    price = FloatField('Precio (Bs)', validators=[DataRequired(), NumberRange(min=0, message='El precio debe ser positivo')])
    original_price = FloatField('Precio Original (opcional)', validators=[Optional(), NumberRange(min=0)])
    is_on_sale = BooleanField('En oferta')
    promo_text = StringField('Texto promocional', validators=[Optional(), Length(max=80)])
    category = SelectField('Categoria', coerce=int, validators=[DataRequired()])
    images = MultipleFileField('Imagenes', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imagenes permitidas')])
    is_new = BooleanField('Novedad')
    is_trending = BooleanField('Tendencia')
    is_featured = BooleanField('Destacado')
    is_active = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category.choices = [
            (c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name).all()
        ]

class UserForm(FlaskForm):
    name = StringField('Nombre completo', validators=[DataRequired(), Length(max=128)])
    username = StringField('Usuario', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Contrasena', validators=[Optional(), Length(min=6)])
    password2 = PasswordField('Confirmar Contrasena', validators=[Optional(), EqualTo('password', 'Las contrasenas no coinciden')])
    is_superadmin = SelectField('Rol', choices=[('0', 'Administrador'), ('1', 'Super Administrador')])
    profile_image = FileField('Foto de perfil', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imagenes permitidas'), Optional()])
    submit = SubmitField('Guardar')

class ProfileForm(FlaskForm):
    name = StringField('Nombre completo', validators=[DataRequired(), Length(max=128)])
    username = StringField('Usuario', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Nueva Contrasena', validators=[Optional(), Length(min=6)])
    password2 = PasswordField('Confirmar Contrasena', validators=[Optional(), EqualTo('password', 'Las contrasenas no coinciden')])
    profile_image = FileField('Foto de perfil', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imagenes permitidas'), Optional()])
    submit = SubmitField('Guardar cambios')

class ThemeForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=50)])
    primary = StringField('Color Primario', validators=[DataRequired(), HEX_COLOR])
    secondary = StringField('Color Secundario', validators=[DataRequired(), HEX_COLOR])
    accent = StringField('Color Acento', validators=[DataRequired(), HEX_COLOR])
    text_color = StringField('Color Texto', validators=[DataRequired(), HEX_COLOR])
    bg_color = StringField('Color Fondo', validators=[DataRequired(), HEX_COLOR])
    success = StringField('Color Exito', validators=[DataRequired(), HEX_COLOR])
    error = StringField('Color Error', validators=[DataRequired(), HEX_COLOR])
    is_default = BooleanField('Tema por defecto')
    submit = SubmitField('Guardar')

class ContactForm(FlaskForm):
    whatsapp = StringField('WhatsApp', validators=[Optional(), Length(max=20)])
    phone = StringField('Telefono', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Length(max=128)])
    tiktok = StringField('TikTok', validators=[Optional(), Length(max=128)])
    facebook = StringField('Facebook', validators=[Optional(), Length(max=256)])
    instagram = StringField('Instagram', validators=[Optional(), Length(max=128)])
    youtube = StringField('YouTube', validators=[Optional(), Length(max=256)])
    telegram = StringField('Telegram', validators=[Optional(), Length(max=128)])
    address = StringField('Direccion', validators=[Optional(), Length(max=256)])
    city = StringField('Ciudad', validators=[Optional(), Length(max=100)])
    schedule = StringField('Horario', validators=[Optional(), Length(max=256)])
    submit = SubmitField('Guardar')

class SiteSettingsForm(FlaskForm):
    site_name = StringField('Nombre del Sitio', validators=[DataRequired(), Length(max=100)])
    tagline = StringField('Lema', validators=[Optional(), Length(max=200)])
    exchange_rate = FloatField('Tipo de Cambio (BS a USD)', validators=[DataRequired(), NumberRange(min=0.1, message='El tipo de cambio debe ser positivo')])
    show_prices = BooleanField('Mostrar Precios')
    maintenance_mode = BooleanField('Modo Mantenimiento')
    qr_image = FileField('QR de pago', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imagenes permitidas'), Optional()])
    submit = SubmitField('Guardar Configuracion')

class CustomOrderForm(FlaskForm):
    client_id = SelectField('Cliente', coerce=int, validators=[InputRequired()])
    new_client_name = StringField('Nombre de cliente', validators=[Optional(), Length(max=128)])
    new_client_phone = StringField('Telefono', validators=[Optional(), Length(max=32)])
    garment_type = SelectField('Tipo de prenda', choices=[(t, t) for t in CUSTOM_ORDER_TYPES], validators=[DataRequired()])
    delivery_date = DateField('Fecha de entrega', validators=[DataRequired(message='Requerido')], format='%Y-%m-%d')
    deposit = FloatField('Monto de adelanto', validators=[Optional(), NumberRange(min=0)])
    total = FloatField('Total', validators=[DataRequired(), NumberRange(min=0)])
    observations = TextAreaField('Observaciones', validators=[Optional()])
    reference_from_garment = BooleanField('Prenda de referencia')
    reference_notes = TextAreaField('Detalle de prenda de referencia', validators=[Optional(), Length(max=300)])
    is_urgent = BooleanField('Urgente')
    status = SelectField(
        'Estado',
        choices=[(s, CUSTOM_ORDER_STATUS_LABELS.get(s, s.title())) for s in CUSTOM_ORDER_STATUSES],
        validators=[DataRequired()]
    )
    images = MultipleFileField('Imagenes', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imagenes permitidas')])
    largo_espalda = StringField('Largo Espalda', validators=[Optional(), Length(max=50)])
    largo_delantero = StringField('Largo Delantero', validators=[Optional(), Length(max=50)])
    cintura = StringField('Cintura', validators=[Optional(), Length(max=50)])
    busto = StringField('Busto', validators=[Optional(), Length(max=50)])
    media_cintura = StringField('Media Cintura', validators=[Optional(), Length(max=50)])
    sisa = StringField('Sisa', validators=[Optional(), Length(max=50)])
    escote = StringField('Escote', validators=[Optional(), Length(max=50)])
    largo_manga = StringField('Largo Manga', validators=[Optional(), Length(max=50)])
    puno = StringField('Puno', validators=[Optional(), Length(max=50)])
    cuello = StringField('Cuello', validators=[Optional(), Length(max=50)])
    abertura = StringField('Abertura', validators=[Optional(), Length(max=50)])
    ancho_espalda = StringField('Ancho Espalda', validators=[Optional(), Length(max=50)])
    figura = StringField('Figura', validators=[Optional(), Length(max=50)])
    alforza = StringField('Alforza', validators=[Optional(), Length(max=50)])
    panos = StringField('Panos', validators=[Optional(), Length(max=50)])
    wato = StringField('Wato', validators=[Optional(), Length(max=50)])
    corridas = StringField('Corridas', validators=[Optional(), Length(max=50)])
    color = StringField('Color', validators=[Optional(), Length(max=50)])
    cadera = StringField('Cadera', validators=[Optional(), Length(max=50)])
    talla = StringField('Talla', validators=[Optional(), Length(max=50)])
    quebrado = StringField('Quebrado', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Guardar pedido')
    items_json = HiddenField('Items')


class CustomOrderItemForm(FlaskForm):
    garment_type = SelectField('Tipo de prenda', choices=[(t, t) for t in CUSTOM_ORDER_TYPES], validators=[DataRequired()])
    observations = TextAreaField('Observaciones', validators=[Optional()])
    reference_from_garment = BooleanField('Prenda de referencia')
    reference_notes = TextAreaField('Detalle de prenda de referencia', validators=[Optional(), Length(max=300)])
    largo_espalda = StringField('Largo Espalda', validators=[Optional(), Length(max=50)])
    largo_delantero = StringField('Largo Delantero', validators=[Optional(), Length(max=50)])
    cintura = StringField('Cintura', validators=[Optional(), Length(max=50)])
    busto = StringField('Busto', validators=[Optional(), Length(max=50)])
    media_cintura = StringField('Media Cintura', validators=[Optional(), Length(max=50)])
    sisa = StringField('Sisa', validators=[Optional(), Length(max=50)])
    escote = StringField('Escote', validators=[Optional(), Length(max=50)])
    largo_manga = StringField('Largo Manga', validators=[Optional(), Length(max=50)])
    puno = StringField('Puno', validators=[Optional(), Length(max=50)])
    cuello = StringField('Cuello', validators=[Optional(), Length(max=50)])
    abertura = StringField('Abertura', validators=[Optional(), Length(max=50)])
    ancho_espalda = StringField('Ancho Espalda', validators=[Optional(), Length(max=50)])
    figura = StringField('Figura', validators=[Optional(), Length(max=50)])
    alforza = StringField('Alforza', validators=[Optional(), Length(max=50)])
    panos = StringField('Panos', validators=[Optional(), Length(max=50)])
    wato = StringField('Wato', validators=[Optional(), Length(max=50)])
    corridas = StringField('Corridas', validators=[Optional(), Length(max=50)])
    color = StringField('Color', validators=[Optional(), Length(max=50)])
    cadera = StringField('Cadera', validators=[Optional(), Length(max=50)])
    talla = StringField('Talla', validators=[Optional(), Length(max=50)])
    quebrado = StringField('Quebrado', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Agregar prenda')

class ClientForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=128)])
    phone = StringField('Telefono', validators=[DataRequired(), Length(max=32)])
    garment_type = SelectField('Tipo de prenda', choices=[(t, t) for t in CUSTOM_ORDER_TYPES])
    largo_espalda = StringField('Largo Espalda', validators=[Optional(), Length(max=50)])
    largo_delantero = StringField('Largo Delantero', validators=[Optional(), Length(max=50)])
    cintura = StringField('Cintura', validators=[Optional(), Length(max=50)])
    busto = StringField('Busto', validators=[Optional(), Length(max=50)])
    media_cintura = StringField('Media Cintura', validators=[Optional(), Length(max=50)])
    sisa = StringField('Sisa', validators=[Optional(), Length(max=50)])
    escote = StringField('Escote', validators=[Optional(), Length(max=50)])
    largo_manga = StringField('Largo Manga', validators=[Optional(), Length(max=50)])
    puno = StringField('Puno', validators=[Optional(), Length(max=50)])
    cuello = StringField('Cuello', validators=[Optional(), Length(max=50)])
    abertura = StringField('Abertura', validators=[Optional(), Length(max=50)])
    ancho_espalda = StringField('Ancho Espalda', validators=[Optional(), Length(max=50)])
    figura = StringField('Figura', validators=[Optional(), Length(max=50)])
    alforza = StringField('Alforza', validators=[Optional(), Length(max=50)])
    panos = StringField('Panos', validators=[Optional(), Length(max=50)])
    wato = StringField('Wato', validators=[Optional(), Length(max=50)])
    corridas = StringField('Corridas', validators=[Optional(), Length(max=50)])
    color = StringField('Color', validators=[Optional(), Length(max=50)])
    cadera = StringField('Cadera', validators=[Optional(), Length(max=50)])
    talla = StringField('Talla', validators=[Optional(), Length(max=50)])
    quebrado = StringField('Quebrado', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Guardar cliente')

# -------------------------------------------------
#                        FUNCIONES AUXILIARES
# -------------------------------------------------

def slugify(text):
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE).strip().lower()
    return re.sub(r'[\s_-]+', '-', text)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file, folder, prefix=''):
    if file and file.filename and allowed_file(file.filename):
        ext = os.path.splitext(file.filename)[1].lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        filename = secure_filename(f"{prefix}{timestamp}{ext}")
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return filename
    return None

def create_notification(message, admin_name, type='info'):
    notif = Notification(message=message, admin_name=admin_name, type=type)
    db.session.add(notif)
    db.session.commit()

def delete_product_assets(product):
    for img in product.images.all():
        img_path = os.path.join(UPLOAD_FOLDER, img.filename)
        if os.path.exists(img_path):
            os.remove(img_path)
    folder_name = f"{slugify(product.name)}_{product.id}"
    product_folder = os.path.join(UPLOAD_FOLDER, folder_name)
    if os.path.isdir(product_folder):
        try:
            for root, dirs, files in os.walk(product_folder, topdown=False):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except OSError:
                        pass
            os.rmdir(product_folder)
        except OSError:
            pass

def delete_custom_order_assets(order):
    folder_name = f"custom_{order.code}_{order.id}"
    order_folder = os.path.join(CUSTOM_ORDER_FOLDER, folder_name)
    for img in order.images.all():
        img_path = os.path.join(CUSTOM_ORDER_FOLDER, img.filename)
        if os.path.exists(img_path):
            os.remove(img_path)
    if os.path.isdir(order_folder):
        try:
            for root, dirs, files in os.walk(order_folder, topdown=False):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except OSError:
                        pass
            os.rmdir(order_folder)
        except OSError:
            pass

def save_custom_order_images(files, order):
    folder_name = f"custom_{order.code}_{order.id}"
    order_folder = os.path.join(CUSTOM_ORDER_FOLDER, folder_name)
    os.makedirs(order_folder, exist_ok=True)
    saved = []
    for f in files:
        if f and f.filename and allowed_file(f.filename):
            filename = save_image(f, order_folder, f'pc_{order.id}_')
            if filename:
                rel = os.path.join(folder_name, filename).replace('\\','/')
                saved.append(rel)
    return saved

def extract_measurements_from_form(form):
    fields = ['largo_espalda','largo_delantero','cintura','busto','media_cintura','sisa','escote','largo_manga','puno','cuello','abertura','ancho_espalda','figura','alforza','panos','wato','corridas','color','cadera','talla','quebrado']
    data = {}
    for f in fields:
        val = getattr(form, f).data if hasattr(form, f) else None
        if val:
            data[f] = val
    return data

def extract_reference_from_form(form):
    """Extra metadata cuando el cliente deja una prenda como referencia."""
    data = {}
    if hasattr(form, 'reference_from_garment') and form.reference_from_garment.data:
        data['referencia_prenda'] = 'Si'
        note = getattr(form, 'reference_notes', None)
        if note and note.data:
            data['nota_referencia'] = note.data
    return data


def append_custom_order_history(order, new_status, note='', user=None):
    """Agrega una entrada de historial dentro del JSON de medidas/meta."""
    data = order.measurements or {}
    history = data.get('_history', [])
    # Hora local Bolivia (UTC-4)
    now = datetime.utcnow() - timedelta(hours=4)
    history.append({
        'fecha': now.strftime('%Y-%m-%d %H:%M:%S (GMT-4)'),
        'fecha_iso': now.isoformat(),
        'estado': new_status,
        'nota': note or '',
        'usuario': user or (current_user.username if current_user and current_user.is_authenticated else 'sistema')
    })
    data['_history'] = history
    order.measurements = data
    # Asegurar que SQLAlchemy marque el cambio en JSON
    try:
        flag_modified(order, 'measurements')
    except Exception:
        pass


def get_custom_order_history(order):
    data = order.measurements or {}
    return data.get('_history', [])

def generate_order_code():
    year = datetime.utcnow().year
    rand = random.randint(0, 999999)
    return f"MP-{year}-{rand:06d}"

def generate_custom_order_code():
    year = datetime.utcnow().year
    rand = random.randint(0, 999999)
    return f"PC-{year}-{rand:06d}"

def append_history(order, status, note=None):
    history = order.history or []
    history.append({'status': status, 'note': note, 'timestamp': datetime.utcnow().isoformat()})
    order.history = history


def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            flash('No tienes permisos para acceder a esta seccion.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ═══════════════════════════════════════════════════════════════════════════

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    """Inyecta variables globales en todos los templates"""
    settings = SiteSettings.query.first()
    exchange_rate = settings.exchange_rate if settings and settings.exchange_rate else app.config.get('PAYPAL_RATE', 6.96)

    # Tema activo
    active_theme = Theme.query.filter_by(is_default=True).first()
    if not active_theme:
        active_theme = Theme.query.first()
    
    # Categorías públicas
    categories = Category.query.filter_by(is_active=True).order_by(Category.order, Category.name).all()
    
    # Información de contacto
    contact = ContactInfo.query.first()
    
    # Notificaciones (solo para admin)
    notifications = []
    if current_user.is_authenticated:
        notifications = Notification.query.order_by(
            Notification.timestamp.desc()
        ).limit(10).all()
    
    return {
        'active_theme': active_theme,
        'site_settings': settings,
        'public_categories': categories,
        'contact_info': contact,
        'notifications': notifications,
        'current_year': datetime.utcnow().year,
        'slugify': slugify,
        'paypal_client_id': app.config.get('PAYPAL_CLIENT_ID'),
        'paypal_rate': exchange_rate,
        'paypal_percent_fee': app.config.get('PAYPAL_PERCENT_FEE', 0),
        'paypal_fixed_fee': app.config.get('PAYPAL_FIXED_FEE', 0),
        'GARMENT_FIELDS': GARMENT_FIELDS,
        'CUSTOM_ORDER_TYPES': CUSTOM_ORDER_TYPES,
        'CUSTOM_ORDER_STATUS_LABELS': CUSTOM_ORDER_STATUS_LABELS,
        'getattr': getattr
    }


# ═══════════════════════════════════════════════════════════════════════════
#                      INICIALIZACIÓN DE DATOS
# ═══════════════════════════════════════════════════════════════════════════

def init_db():
    """Inicializa la base de datos con datos por defecto"""
    db.create_all()
    
    # Crear tema por defecto si no existe
    if Theme.query.count() == 0:
        themes_data = [
            ('Elegante', '#8F2D56', '#E36485', '#25D366', '#333333', '#F8F9FA', '#2A9D8F', '#E63946', True),
            ('Oscuro', '#1a1a2e', '#16213e', '#e94560', '#eaeaea', '#1a1a2e', '#00b894', '#ff6b6b', False),
            ('Moderno', '#667eea', '#764ba2', '#f093fb', '#2d3436', '#ffffff', '#00cec9', '#ff7675', False),
            ('Natural', '#2d5a27', '#4a7c59', '#a8d8b9', '#1e3d19', '#f5f5dc', '#27ae60', '#e74c3c', False),
            ('Coral', '#ff6b6b', '#ee5a5a', '#feca57', '#2d3436', '#fff5f5', '#1dd1a1', '#ff6b6b', False),
        ]
        
        for data in themes_data:
            theme = Theme(
                name=data[0], primary=data[1], secondary=data[2], accent=data[3],
                text_color=data[4], bg_color=data[5], success=data[6], error=data[7],
                is_default=data[8]
            )
            db.session.add(theme)
    
    # Crear información de contacto si no existe
    if ContactInfo.query.count() == 0:
        contact = ContactInfo(
            whatsapp='59170000000',
            city='Sucre, Bolivia',
            schedule='Lun - Sáb: 9:00 - 19:00'
        )
        db.session.add(contact)
    
    # Crear usuario admin por defecto si no existe
    if User.query.count() == 0:
        admin = User(
            username='admin',
            name='Administrador',
            is_superadmin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        print('✓ Usuario admin creado (usuario: admin, contraseña: admin123)')
    
    db.session.commit()


# ═══════════════════════════════════════════════════════════════════════════
#                        RUTAS PÚBLICAS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Página principal"""
    novedades = Product.query.filter_by(is_new=True, is_active=True).limit(8).all()
    tendencias = Product.query.filter_by(is_trending=True, is_active=True).limit(8).all()
    destacados = Product.query.filter_by(is_featured=True, is_active=True).limit(8).all()
    productos = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(12).all()
    
    # Mezclar para variedad
    random.shuffle(novedades)
    random.shuffle(tendencias)
    random.shuffle(destacados)
    
    return render_template('public/index.html',
        novedades=novedades,
        tendencias=tendencias,
        destacados=destacados,
        productos=productos
    )


@app.route('/catalogo')
def catalogo():
    """Catálogo de productos con filtros y paginación"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    q = request.args.get('q', '', type=str).strip()
    categoria_id = request.args.get('categoria', type=int)
    sort = request.args.get('sort', 'recientes', type=str)
    
    query = Product.query.filter_by(is_active=True)
    
    # Filtro por categoría
    if categoria_id:
        query = query.filter_by(category_id=categoria_id)
    
    # Búsqueda
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(Product.name.ilike(search), Product.description.ilike(search))
        )
    
    # Ordenamiento
    sort_options = {
        'recientes': Product.created_at.desc(),
        'antiguos': Product.created_at.asc(),
        'precio_asc': Product.price.asc(),
        'precio_desc': Product.price.desc(),
        'nombre_asc': Product.name.asc(),
        'nombre_desc': Product.name.desc(),
        'populares': Product.views.desc()
    }
    query = query.order_by(sort_options.get(sort, Product.created_at.desc()))
    
    # Paginación
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    
    categoria = Category.query.get(categoria_id) if categoria_id else None
    categorias = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    
    return render_template('public/catalogo.html',
        productos=pagination.items,
        categoria=categoria,
        categorias=categorias,
        search=q,
        sort=sort,
        pagination=pagination,
        per_page=per_page
    )


@app.route('/producto/<int:id>')
def producto_detalle_legacy(id):
    """Redirección a URL SEO-friendly"""
    producto = Product.query.get_or_404(id)
    return redirect(url_for('producto_detalle', id=id, slug=slugify(producto.name)), code=301)


@app.route('/p/<slug>-<int:id>')
def producto_detalle(slug, id):
    """Página de detalle de producto"""
    producto = Product.query.get_or_404(id)
    
    # Incrementar vistas
    producto.views += 1
    db.session.commit()
    
    # Productos relacionados
    relacionados = Product.query.filter(
        Product.category_id == producto.category_id,
        Product.id != producto.id,
        Product.is_active == True
    ).limit(4).all()
    
    return render_template('public/producto_detalle.html',
        producto=producto,
        relacionados=relacionados
    )


@app.route('/quienes-somos')
def quienes_somos():
    """Página Quiénes Somos"""
    return render_template('public/quienes_somos.html')


@app.route('/contacto')
def contacto():
    """Página de Contacto"""
    return render_template('public/contacto.html')


@app.route('/rastrear-pedido', methods=['GET', 'POST'])
def rastrear_pedido():
    """Página pública para rastrear pedidos"""
    code = (request.args.get('code') or request.form.get('code') or '').strip().upper()
    pedido = None
    if code:
        pedido = Order.query.filter_by(order_code=code).first()
        if not pedido:
            flash('No se encontró un pedido con ese código.', 'warning')
    return render_template('public/rastrear_pedido.html', pedido=pedido, code=code, statuses=ORDER_STATUSES)


@app.route('/pedido/<order_code>')
def pedido_confirmado(order_code):
    """Página de confirmación de pedido"""
    pedido = Order.query.filter_by(order_code=order_code.upper()).first_or_404()
    return render_template('public/pedido_confirmado.html', pedido=pedido)


@app.route('/api/pedidos/<order_code>')
def api_pedido(order_code):
    """Endpoint de rastreo en JSON"""
    pedido = Order.query.filter_by(order_code=order_code.upper()).first_or_404()
    return jsonify({
        'order_code': pedido.order_code,
        'product': pedido.product.name if pedido.product else '',
        'image_url': pedido.image_url,
        'payment_method': pedido.payment_method,
        'total': pedido.total,
        'status': pedido.status,
        'history': pedido.history or [],
        'created_at': pedido.created_at.isoformat()
    })


# -------------------------------------------------
#                 CHECKOUT / ORDERS
# -------------------------------------------------


def paypal_api_base():
    """Devuelve la URL base de PayPal segun entorno."""
    env = (app.config.get('PAYPAL_ENVIRONMENT') or 'sandbox').lower()
    return 'https://api-m.paypal.com' if env in ('live', 'production') else 'https://api-m.sandbox.paypal.com'


def compute_paypal_total_usd(bs_amount):
    """Calcula el monto en USD incluyendo comision de PayPal."""
    # Obtener tasa de cambio de la BD
    settings = SiteSettings.query.first()
    rate = settings.exchange_rate if settings and settings.exchange_rate else 6.96
    
    percent = float(app.config.get('PAYPAL_PERCENT_FEE') or 0)
    fixed = float(app.config.get('PAYPAL_FIXED_FEE') or 0)
    
    if rate <= 0:
        rate = 6.96
        
    net = bs_amount / rate
    denominator = (1 - percent) if percent < 1 else 1
    gross = (net + fixed) / denominator
    return round(gross, 2)




def extract_measurements_from_form(form):
    """Construye un diccionario de medidas desde el formulario"""
    fields = [
        'largo_espalda','largo_delantero','cintura','busto','media_cintura','sisa','escote',
        'largo_manga','puno','cuello','abertura','ancho_espalda','figura',
        'alforza','panos','wato','corridas','color','cadera','talla','quebrado'
    ]
    data = {}
    for f in fields:
        val = getattr(form, f).data if hasattr(form, f) else None
        if val:
            data[f] = val
    return data

def paypal_get_token():
    """Obtiene token OAuth de PayPal."""
    client_id = app.config.get('PAYPAL_CLIENT_ID')
    secret = app.config.get('PAYPAL_SECRET')
    if not client_id or not secret:
        abort(500, description='Faltan credenciales de PayPal')
    try:
        resp = requests.post(
            f"{paypal_api_base()}/v1/oauth2/token",
            data={'grant_type': 'client_credentials'},
            auth=(client_id, secret),
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('access_token')
    except requests.RequestException as exc:
        app.logger.exception('Error obteniendo token de PayPal: %s', exc)
        abort(502, description='No se pudo conectar con PayPal')


def paypal_create_order(amount_usd, product):
    """Crea una orden de PayPal y devuelve su payload."""
    token = paypal_get_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'intent': 'CAPTURE',
        'purchase_units': [{
            'amount': {
                'currency_code': 'USD',
                'value': f"{amount_usd:.2f}"
            },
            'custom_id': str(product.id),
            'description': product.name[:127] if product and product.name else 'Pedido Modas Pathy'
        }],
        'application_context': {
            'brand_name': app.config.get('STORE_NAME', 'Modas Pathy'),
            'shipping_preference': 'NO_SHIPPING',
            'user_action': 'PAY_NOW'
        }
    }
    try:
        resp = requests.post(
            f"{paypal_api_base()}/v2/checkout/orders",
            json=payload,
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        app.logger.exception('Error creando orden PayPal: %s', exc)
        abort(502, description='No se pudo crear la orden en PayPal')


def paypal_capture_order(order_id):
    """Captura una orden PayPal existente."""
    token = paypal_get_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    try:
        resp = requests.post(
            f"{paypal_api_base()}/v2/checkout/orders/{order_id}/capture",
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        app.logger.exception('Error capturando orden PayPal %s: %s', order_id, exc)
        abort(502, description='No se pudo capturar el pago en PayPal')


def _create_order(product_id, image_url, payment_method, total=None, customer_name=None, customer_phone=None, order_notes=None):
    """Crea y persiste un pedido"""
    product = Product.query.get_or_404(product_id)
    code = generate_order_code()
    while Order.query.filter_by(order_code=code).first():
        code = generate_order_code()
    order = Order(
        order_code=code,
        product_id=product.id,
        image_url=image_url,
        payment_method=payment_method,
        total=total or product.price,
        status='Pagado' if payment_method == 'paypal' else 'Recibido',
        customer_name=customer_name,
        customer_phone=customer_phone,
        order_notes=order_notes
    )
    append_history(order, order.status, note=f'Creado via {payment_method}')
    db.session.add(order)
    db.session.commit()
    return order


@app.route('/api/checkout/paypal', methods=['POST'])
def checkout_paypal():
    """Crea una orden PayPal (sin generar pedido hasta capturar)."""
    data = request.get_json(force=True, silent=True) or {}
    product_id = data.get('product_id')
    image_url = (data.get('image_url') or '').strip()
    order_notes = (data.get('order_notes') or '').strip()
    
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        abort(400, description='Producto invalido')
    
    product = Product.query.get_or_404(product_id)
    bs_total = product.price
    usd_total = compute_paypal_total_usd(bs_total)
    
    order_payload = paypal_create_order(usd_total, product)
    order_id = order_payload.get('id')
    if not order_id:
        abort(502, description='PayPal no devolvio ID de orden')
    
    return jsonify({
        'order_id': order_id,
        'amount_usd': usd_total,
        'order_notes': order_notes
    })


@app.route('/api/checkout/paypal/capture', methods=['POST'])
def checkout_paypal_capture():
    """Captura el pago de PayPal y genera el pedido."""
    data = request.get_json(force=True, silent=True) or {}
    order_id = data.get('order_id')
    image_url = (data.get('image_url') or '').strip()
    order_notes = (data.get('order_notes') or '').strip()
    
    if not order_id:
        abort(400, description='Falta el ID de orden de PayPal')
    
    capture_data = paypal_capture_order(order_id)
    
    if capture_data.get('status') != 'COMPLETED':
        abort(400, description='El pago no se completo en PayPal')
    
    purchase_units = capture_data.get('purchase_units') or []
    product_id = None
    capture_id = None
    
    if purchase_units:
        custom_id = purchase_units[0].get('custom_id')
        try:
            product_id = int(custom_id)
        except (TypeError, ValueError):
            product_id = None
        
        payments = purchase_units[0].get('payments') or {}
        captures = payments.get('captures') or []
        if captures:
            capture_id = captures[0].get('id')
    
    if not product_id:
        abort(400, description='No se pudo asociar el producto al pago')
    
    product = Product.query.get_or_404(product_id)
    order = _create_order(product.id, image_url, 'paypal', total=product.price, order_notes=order_notes)
    note = f'Pago PayPal confirmado (capture {capture_id})' if capture_id else 'Pago PayPal confirmado'
    append_history(order, 'Pagado', note=note)
    db.session.commit()
    
    return jsonify({
        'order_code': order.order_code,
        'redirect_url': url_for('pedido_confirmado', order_code=order.order_code)
    })


@app.route('/api/checkout/whatsapp', methods=['POST'])
def checkout_whatsapp():
    """Genera pedido iniciado por WhatsApp"""
    data = request.get_json(force=True, silent=True) or {}
    product_id = data.get('product_id')
    image_url = (data.get('image_url') or '').strip()
    order_notes = (data.get('order_notes') or '').strip()
    try:
        total = float(data.get('total')) if data.get('total') is not None else None
    except (TypeError, ValueError):
        total = None
    
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        abort(400, description='Producto inválido')
    
    order = _create_order(product_id, image_url, 'whatsapp', total=total, order_notes=order_notes)
    
    return jsonify({
        'order_code': order.order_code,
        'redirect_url': url_for('pedido_confirmado', order_code=order.order_code)
    })


@app.route('/api/checkout/qr', methods=['POST'])
def checkout_qr():
    """Genera pedido iniciado por QR"""
    data = request.get_json(force=True, silent=True) or {}
    product_id = data.get('product_id')
    image_url = (data.get('image_url') or '').strip()
    order_notes = (data.get('order_notes') or '').strip()
    try:
        total = float(data.get('total')) if data.get('total') is not None else None
    except (TypeError, ValueError):
        total = None
    
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        abort(400, description='Producto invalido')
    
    order = _create_order(product_id, image_url, 'qr', total=total, order_notes=order_notes)
    
    return jsonify({
        'order_code': order.order_code,
        'redirect_url': url_for('pedido_confirmado', order_code=order.order_code)
    })


# ═══════════════════════════════════════════════════════════════════════════
#                            SEO
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/robots.txt')
def robots_txt():
    """Archivo robots.txt para SEO"""
    base = request.url_root.rstrip('/')
    content = f"""User-agent: *
Allow: /
Disallow: /admin/

Sitemap: {base}/sitemap.xml
"""
    return Response(content, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    """Sitemap XML para SEO"""
    base = request.url_root.rstrip('/')
    
    urls = []
    
    # Páginas estáticas
    static_pages = ['index', 'catalogo', 'quienes_somos', 'contacto']
    for page in static_pages:
        urls.append(f'<url><loc>{base}{url_for(page)}</loc><priority>0.8</priority></url>')
    
    # Productos
    for p in Product.query.filter_by(is_active=True).all():
        loc = f"{base}{url_for('producto_detalle', id=p.id, slug=slugify(p.name))}"
        urls.append(f'<url><loc>{loc}</loc><priority>0.6</priority></url>')
    
    # Categorías
    for c in Category.query.filter_by(is_active=True).all():
        loc = f"{base}{url_for('catalogo', categoria=c.id)}"
        urls.append(f'<url><loc>{loc}</loc><priority>0.7</priority></url>')
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""
    
    return Response(xml, mimetype='application/xml')


# ═══════════════════════════════════════════════════════════════════════════
#                       AUTENTICACIÓN ADMIN
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Inicio de sesión de administrador"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        
        if user and user.check_password(form.password.data):
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            login_user(user, remember=form.remember.data)
            flash(f'¡Bienvenido, {user.name or user.username}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin_dashboard'))
        
        flash('Usuario o contraseña incorrectos.', 'danger')
    
    return render_template('admin/login.html', form=form)


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('admin_login'))


# ═══════════════════════════════════════════════════════════════════════════
#                       PANEL DE ADMINISTRACIÓN
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
def admin_dashboard():
    """Dashboard principal del admin"""
    stats = {
        'productos': Product.query.count(),
        'categorias': Category.query.count(),
        'usuarios': User.query.count(),
        'productos_activos': Product.query.filter_by(is_active=True).count(),
        'novedades': Product.query.filter_by(is_new=True).count(),
        'tendencias': Product.query.filter_by(is_trending=True).count(),
        'destacados': Product.query.filter_by(is_featured=True).count(),
    }
    
    # Productos más vistos
    top_productos = Product.query.order_by(Product.views.desc()).limit(5).all()
    
    # Últimas notificaciones
    notificaciones = Notification.query.order_by(Notification.timestamp.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
        stats=stats,
        top_productos=top_productos,
        notificaciones=notificaciones
    )


# ═══════════════════════════════════════════════════════════════════════════
#                      CRUD CATEGORÍAS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/categorias', methods=['GET', 'POST'])
@login_required
def admin_categorias():
    """Listado y creación de categorías"""
    form = CategoryForm()
    
    if form.validate_on_submit():
        if Category.query.filter_by(name=form.name.data).first():
            flash('Ya existe una categoría con ese nombre.', 'warning')
        else:
            categoria = Category(
                name=form.name.data,
                slug=slugify(form.name.data),
                description=form.description.data,
                icon=form.icon.data or 'bi-tag',
                is_active=form.is_active.data
            )
            db.session.add(categoria)
            db.session.commit()
            
            create_notification(f'Nueva categoría: {categoria.name}', current_user.username, 'success')
            flash('Categoría creada correctamente.', 'success')
            return redirect(url_for('admin_categorias'))
    
    categorias = Category.query.order_by(Category.order, Category.name).all()
    return render_template('admin/categorias.html', form=form, categorias=categorias)


@app.route('/admin/categorias/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_categoria_editar(id):
    """Edición de categoría"""
    categoria = Category.query.get_or_404(id)
    form = CategoryForm(obj=categoria)
    
    if form.validate_on_submit():
        existing = Category.query.filter_by(name=form.name.data).first()
        if existing and existing.id != id:
            flash('Ya existe una categoría con ese nombre.', 'warning')
        else:
            categoria.name = form.name.data
            categoria.slug = slugify(form.name.data)
            categoria.description = form.description.data
            categoria.icon = form.icon.data or 'bi-tag'
            categoria.is_active = form.is_active.data
            db.session.commit()
            
            flash('Categoría actualizada.', 'success')
            return redirect(url_for('admin_categorias'))
    
    return render_template('admin/categoria_edit.html', form=form, categoria=categoria)


@app.route('/admin/categorias/eliminar/<int:id>', methods=['POST'])
@login_required
def admin_categoria_eliminar(id):
    """Eliminación de categoría"""
    categoria = Category.query.get_or_404(id)
    nombre = categoria.name
    
    # Verificar si tiene productos
    if categoria.products.count() > 0:
        flash(f'No se puede eliminar. La categoría tiene {categoria.products.count()} productos asociados.', 'danger')
        return redirect(url_for('admin_categorias'))
    
    db.session.delete(categoria)
    db.session.commit()
    
    create_notification(f'Categoría eliminada: {nombre}', current_user.username, 'warning')
    flash('Categoría eliminada.', 'warning')
    return redirect(url_for('admin_categorias'))


# ═══════════════════════════════════════════════════════════════════════════
#                        CRUD PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/productos')
@login_required
def admin_productos():
    """Listado de productos"""
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    categoria_id = request.args.get('categoria', type=int)
    
    query = Product.query
    
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    if categoria_id:
        query = query.filter_by(category_id=categoria_id)
    
    pagination = db.paginate(query.order_by(Product.created_at.desc()), page=page, per_page=15)
    categorias = Category.query.filter_by(is_active=True).all()
    
    return render_template('admin/productos.html',
        productos=pagination.items,
        pagination=pagination,
        categorias=categorias,
        search=q,
        categoria_id=categoria_id
    )


@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
@login_required
def admin_producto_nuevo():
    """Creación de producto"""
    form = ProductForm()
    
    if form.validate_on_submit():
        promo_text = (form.promo_text.data or '').strip()
        producto = Product(
            name=form.name.data,
            slug=slugify(form.name.data),
            description=form.description.data,
            price=form.price.data,
            original_price=form.original_price.data,
            is_on_sale=form.is_on_sale.data,
            promo_text=promo_text or None,
            category_id=form.category.data,
            is_new=form.is_new.data,
            is_trending=form.is_trending.data,
            is_featured=form.is_featured.data,
            is_active=form.is_active.data
        )
        db.session.add(producto)
        db.session.commit()
        
        # Procesar imágenes
        files = request.files.getlist('images')
        main_index = int(request.form.get('main_image_index', 0))
        
        # Crear carpeta del producto
        folder_name = f"{slugify(producto.name)}_{producto.id}"
        product_folder = os.path.join(UPLOAD_FOLDER, folder_name)
        os.makedirs(product_folder, exist_ok=True)
        
        for i, f in enumerate(files):
            if f and f.filename and allowed_file(f.filename):
                filename = save_image(f, product_folder, f'prod_{producto.id}_')
                if filename:
                    img = ProductImage(
                        filename=os.path.join(folder_name, filename).replace('\\', '/'),
                        is_main=(i == main_index),
                        order=i,
                        product_id=producto.id
                    )
                    db.session.add(img)
        
        db.session.commit()
        create_notification(f'Nuevo producto: {producto.name}', current_user.username, 'success')
        flash('Producto creado correctamente.', 'success')
        return redirect(url_for('admin_productos'))
    
    return render_template('admin/producto_form.html', form=form, nuevo=True, images=[])


@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_producto_editar(id):
    """Edición de producto"""
    producto = Product.query.get_or_404(id)
    form = ProductForm(obj=producto)
    
    if form.validate_on_submit():
        promo_text = (form.promo_text.data or '').strip()
        producto.name = form.name.data
        producto.slug = slugify(form.name.data)
        producto.description = form.description.data
        producto.price = form.price.data
        producto.original_price = form.original_price.data
        producto.is_on_sale = form.is_on_sale.data
        producto.promo_text = promo_text or None
        producto.category_id = form.category.data
        producto.is_new = form.is_new.data
        producto.is_trending = form.is_trending.data
        producto.is_featured = form.is_featured.data
        producto.is_active = form.is_active.data
        
        # Eliminar imágenes marcadas
        delete_ids = request.form.getlist('delete_image_ids')
        for img_id in delete_ids:
            img = ProductImage.query.get(int(img_id))
            if img:
                img_path = os.path.join(UPLOAD_FOLDER, img.filename)
                if os.path.exists(img_path):
                    os.remove(img_path)
                db.session.delete(img)
        
        # Manejar imagen principal
        raw_main = request.form.get('main_image_index', '')
        is_existing = raw_main.startswith('b_')
        main_val = raw_main[2:] if is_existing else raw_main
        
        # Reset todas como no principales
        for img in producto.images.all():
            img.is_main = is_existing and str(img.id) == main_val
        
        # Nuevas imágenes
        files = request.files.getlist('images')
        folder_name = f"{slugify(producto.name)}_{producto.id}"
        product_folder = os.path.join(UPLOAD_FOLDER, folder_name)
        os.makedirs(product_folder, exist_ok=True)
        
        try:
            main_int = int(main_val) if main_val and not is_existing else None
        except ValueError:
            main_int = None
        
        for i, f in enumerate(files):
            if f and f.filename and allowed_file(f.filename):
                filename = save_image(f, product_folder, f'prod_{producto.id}_')
                if filename:
                    img = ProductImage(
                        filename=os.path.join(folder_name, filename).replace('\\', '/'),
                        is_main=(not is_existing and i == main_int),
                        order=producto.images.count() + i,
                        product_id=producto.id
                    )
                    db.session.add(img)
        
        db.session.commit()
        create_notification(f'Producto editado: {producto.name}', current_user.username, 'info')
        flash('Producto actualizado.', 'success')
        return redirect(url_for('admin_productos'))
    
    return render_template('admin/producto_form.html',
        form=form,
        nuevo=False,
        images=producto.images.order_by(ProductImage.order).all()
    )


@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
@login_required
def admin_producto_eliminar(id):
    """Eliminación de producto"""
    producto = Product.query.get_or_404(id)
    nombre = producto.name
    
    # Eliminar pedidos relacionados
    for pedido in Order.query.filter_by(product_id=producto.id).all():
        db.session.delete(pedido)
    
    # Eliminar imágenes y carpeta
    delete_product_assets(producto)
    
    db.session.delete(producto)
    db.session.commit()
    
    create_notification(f'Producto eliminado: {nombre}', current_user.username, 'warning')
    flash('Producto eliminado.', 'warning')
    return redirect(url_for('admin_productos'))


# ═══════════════════════════════════════════════════════════════════════════
#                         PERFIL DE USUARIO
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/perfil')
@login_required
def admin_profile():
    """Ver perfil del usuario"""
    return render_template('admin/profile.html')


@app.route('/admin/perfil/editar', methods=['GET', 'POST'])
@login_required
def admin_profile_edit():
    """Editar perfil del usuario"""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        # Verificar username único
        existing = User.query.filter_by(username=form.username.data).first()
        if existing and existing.id != current_user.id:
            flash('Ese nombre de usuario ya está en uso.', 'warning')
            return render_template('admin/profile_edit.html', form=form)
        
        current_user.name = form.name.data
        current_user.username = form.username.data
        
        if form.password.data:
            current_user.set_password(form.password.data)
        
        if form.profile_image.data:
            # Eliminar imagen anterior
            if current_user.profile_image:
                old_path = os.path.join(PROFILE_FOLDER, current_user.profile_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            filename = save_image(form.profile_image.data, PROFILE_FOLDER, f'profile_{current_user.id}_')
            if filename:
                current_user.profile_image = filename
        
        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('admin_profile'))
    
    return render_template('admin/profile_edit.html', form=form)


# ═══════════════════════════════════════════════════════════════════════════
#                       GESTIÓN DE USUARIOS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/usuarios')
@login_required
@superadmin_required
def admin_usuarios():
    """Listado de usuarios"""
    usuarios = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)


@app.route('/admin/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_usuario_nuevo():
    """Crear nuevo usuario"""
    form = UserForm()
    
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Ese nombre de usuario ya existe.', 'warning')
        elif not form.password.data:
            flash('La contraseña es requerida para nuevos usuarios.', 'danger')
        else:
            user = User(
                username=form.username.data,
                name=form.name.data,
                is_superadmin=(form.is_superadmin.data == '1')
            )
            user.set_password(form.password.data)
            
            if form.profile_image.data:
                filename = save_image(form.profile_image.data, PROFILE_FOLDER, f'profile_{form.username.data}_')
                if filename:
                    user.profile_image = filename
            
            db.session.add(user)
            db.session.commit()
            
            create_notification(f'Nuevo administrador: {user.username}', current_user.username, 'success')
            flash('Usuario creado correctamente.', 'success')
            return redirect(url_for('admin_usuarios'))
    
    return render_template('admin/usuario_form.html', form=form, nuevo=True)


@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_usuario_editar(id):
    """Editar usuario"""
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    form.is_superadmin.data = '1' if user.is_superadmin else '0'
    
    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data).first()
        if existing and existing.id != id:
            flash('Ese nombre de usuario ya está en uso.', 'warning')
        else:
            user.name = form.name.data
            user.username = form.username.data
            user.is_superadmin = (request.form.get('is_superadmin') == '1')
            
            if form.password.data:
                user.set_password(form.password.data)
            
            if form.profile_image.data:
                if user.profile_image:
                    old_path = os.path.join(PROFILE_FOLDER, user.profile_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = save_image(form.profile_image.data, PROFILE_FOLDER, f'profile_{user.id}_')
                if filename:
                    user.profile_image = filename
            
            db.session.commit()
            flash('Usuario actualizado.', 'success')
            return redirect(url_for('admin_usuarios'))
    
    return render_template('admin/usuario_form.html', form=form, nuevo=False, user=user)


@app.route('/admin/usuarios/eliminar/<int:id>', methods=['POST'])
@login_required
@superadmin_required
def admin_usuario_eliminar(id):
    """Eliminar usuario"""
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('admin_usuarios'))
    
    if user.profile_image:
        img_path = os.path.join(PROFILE_FOLDER, user.profile_image)
        if os.path.exists(img_path):
            os.remove(img_path)
    
    nombre = user.username
    db.session.delete(user)
    db.session.commit()
    
    create_notification(f'Usuario eliminado: {nombre}', current_user.username, 'warning')
    flash('Usuario eliminado.', 'warning')
    return redirect(url_for('admin_usuarios'))


# ═══════════════════════════════════════════════════════════════════════════
#                         GESTIÓN DE TEMAS
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/temas')
@login_required
@superadmin_required
def admin_themes():
    """Listado de temas"""
    temas = Theme.query.order_by(Theme.created_at.desc()).all()
    return render_template('admin/themes.html', temas=temas)


@app.route('/admin/temas/nuevo', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_theme_nuevo():
    """Crear tema"""
    form = ThemeForm()
    
    if form.validate_on_submit():
        if form.is_default.data:
            Theme.query.update({Theme.is_default: False})
        
        tema = Theme(
            name=form.name.data,
            primary=form.primary.data,
            secondary=form.secondary.data,
            accent=form.accent.data,
            text_color=form.text_color.data,
            bg_color=form.bg_color.data,
            success=form.success.data,
            error=form.error.data,
            is_default=form.is_default.data
        )
        db.session.add(tema)
        db.session.commit()
        
        flash('Tema creado correctamente.', 'success')
        return redirect(url_for('admin_themes'))
    
    return render_template('admin/theme_form.html', form=form, titulo='Nuevo Tema')


@app.route('/admin/temas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_theme_editar(id):
    """Editar tema"""
    tema = Theme.query.get_or_404(id)
    form = ThemeForm(obj=tema)
    
    if form.validate_on_submit():
        if form.is_default.data:
            Theme.query.update({Theme.is_default: False})
        
        form.populate_obj(tema)
        db.session.commit()
        
        flash('Tema actualizado.', 'success')
        return redirect(url_for('admin_themes'))
    
    return render_template('admin/theme_form.html', form=form, titulo='Editar Tema')


@app.route('/admin/temas/eliminar/<int:id>', methods=['POST'])
@login_required
@superadmin_required
def admin_theme_eliminar(id):
    """Eliminar tema"""
    tema = Theme.query.get_or_404(id)
    
    if tema.is_default:
        flash('No puedes eliminar el tema activo.', 'danger')
        return redirect(url_for('admin_themes'))
    
    db.session.delete(tema)
    db.session.commit()
    
    flash('Tema eliminado.', 'warning')
    return redirect(url_for('admin_themes'))


@app.route('/admin/temas/activar', methods=['POST'])
@login_required
@superadmin_required
def admin_theme_activar():
    """Activar tema"""
    tema_id = request.form.get('theme_id', type=int)
    
    if tema_id:
        Theme.query.update({Theme.is_default: False})
        tema = Theme.query.get_or_404(tema_id)
        tema.is_default = True
        db.session.commit()
        flash(f'Tema "{tema.name}" activado.', 'success')
    
    return redirect(request.referrer or url_for('admin_dashboard'))


# ═══════════════════════════════════════════════════════════════════════════
#                     INFORMACIÓN DE CONTACTO
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/admin/contacto', methods=['GET', 'POST'])
@login_required
def admin_contactos():
    """Gestión de información de contacto"""
    info = ContactInfo.query.first()
    if not info:
        info = ContactInfo()
        db.session.add(info)
        db.session.commit()
    
    form = ContactForm(obj=info)
    
    if form.validate_on_submit():
        form.populate_obj(info)
        db.session.commit()
        flash('Información de contacto actualizada.', 'success')
        return redirect(url_for('admin_contactos'))
    
    return render_template('admin/contactos.html', form=form)


@app.route('/admin/configuracion', methods=['GET', 'POST'])
@login_required
@superadmin_required
def admin_settings():
    """Gestión de configuración del sitio"""
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings()
        db.session.add(settings)
        db.session.commit()
    
    form = SiteSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        settings.site_name = form.site_name.data
        settings.tagline = form.tagline.data
        settings.exchange_rate = form.exchange_rate.data
        settings.show_prices = form.show_prices.data
        settings.maintenance_mode = form.maintenance_mode.data
        
        if form.qr_image.data:
            if settings.qr_image:
                old_path = os.path.join(QR_FOLDER, settings.qr_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = save_image(form.qr_image.data, QR_FOLDER, 'qr_')
            if filename:
                settings.qr_image = filename
        
        db.session.commit()
        flash('Configuración actualizada correctamente.', 'success')
        return redirect(url_for('admin_settings'))
    
    return render_template('admin/settings.html', form=form, settings=settings)


# -------------------------------------------------
#                        PEDIDOS
# -------------------------------------------------


@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    """Listado de pedidos"""
    pedidos = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos, statuses=ORDER_STATUSES)


@app.route('/admin/pedidos/<int:order_id>/estado', methods=['POST'])
@login_required
def admin_pedido_estado(order_id):
    """Actualiza el estado de un pedido"""
    pedido = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status and new_status in ORDER_STATUSES:
        pedido.status = new_status
        append_history(pedido, new_status, note=f'Actualizado por {current_user.username}')
        db.session.commit()
        flash('Estado actualizado correctamente.', 'success')
    else:
        flash('Estado inválido.', 'warning')
    return redirect(request.referrer or url_for('admin_pedidos'))


@app.route('/admin/pedidos/eliminar/<int:order_id>', methods=['POST'])
@login_required
def admin_pedido_eliminar(order_id):
    """Eliminar pedido individual"""
    pedido = Order.query.get_or_404(order_id)
    code = pedido.order_code
    db.session.delete(pedido)
    db.session.commit()
    flash(f'Pedido {code} eliminado.', 'warning')
    return redirect(request.referrer or url_for('admin_pedidos'))


# ═══════════════════════════════════════════════════════════════════════════
#                       # -------------------------------------------------
#              PEDIDOS PERSONALIZADOS
# -------------------------------------------------


def _custom_order_client_choices():
    choices = [(0, 'Nuevo cliente')]
    for c in Client.query.order_by(Client.name).all():
        label = f"{c.name} ({c.phone})"
        choices.append((c.id, label))
    return choices


@app.route('/admin/pedidos-personalizados')
@login_required
def admin_custom_orders():
    """Listado de pedidos personalizados"""
    page = request.args.get('page', 1, type=int)
    client_id = request.args.get('cliente', type=int)
    garment = request.args.get('tipo', '', type=str)
    estado = request.args.get('estado', '', type=str)
    urgente = request.args.get('urgente', type=str)

    query = CustomOrder.query.join(Client)
    if client_id:
        query = query.filter(CustomOrder.client_id == client_id)
    if garment:
        query = query.filter(CustomOrder.garment_type == garment)
    if estado:
        query = query.filter(CustomOrder.status == estado)
    if urgente == '1':
        query = query.filter(CustomOrder.is_urgent == True)

    pagination = db.paginate(query.order_by(CustomOrder.created_at.desc()), page=page, per_page=15, error_out=False)
    clients = Client.query.order_by(Client.name).all()
    today = datetime.utcnow().date()
    soon_orders = CustomOrder.query.filter(
        CustomOrder.delivery_date != None
    ).filter(
        CustomOrder.delivery_date <= today + timedelta(days=3)
    ).order_by(CustomOrder.delivery_date.asc()).all()
    agenda_items = CustomOrder.query.filter(CustomOrder.delivery_date != None).order_by(CustomOrder.delivery_date.asc(), CustomOrder.is_urgent.desc()).limit(100).all()
    urgentes_count = CustomOrder.query.filter_by(is_urgent=True).count()

    return render_template('admin/custom_orders.html',
        pedidos=pagination.items,
        pagination=pagination,
        clients=clients,
        tipos=CUSTOM_ORDER_TYPES,
        estados=CUSTOM_ORDER_STATUSES,
        estado_labels=CUSTOM_ORDER_STATUS_LABELS,
        filtro_cliente=client_id,
        filtro_tipo=garment,
        filtro_estado=estado,
        filtro_urgente=urgente,
        agenda_items=agenda_items,
        urgentes_count=urgentes_count,
        now_date=today,
        soon_orders=soon_orders
    )


@app.route('/admin/pedidos-personalizados/nuevo', methods=['GET', 'POST'])
@login_required
def admin_custom_order_nuevo():
    """Crear pedido personalizado"""
    form = CustomOrderForm()
    form.client_id.choices = _custom_order_client_choices()
    prefill_client = request.args.get('cliente', type=int)
    if request.method == 'GET':
        if prefill_client:
            form.client_id.data = prefill_client
        elif not form.client_id.data:
            form.client_id.data = 0

    if form.validate_on_submit():
        # Validar items en JSON
        import json
        raw_items = request.form.get('items_json') or ''
        try:
            items_data = json.loads(raw_items) if raw_items else []
        except Exception:
            items_data = []
        if not items_data:
            flash('Debes agregar al menos una prenda al pedido.', 'warning')
            return render_template('admin/custom_order_form.html', form=form, nuevo=True)
        
        if not form.delivery_date.data:
            flash('La fecha de entrega es obligatoria.', 'warning')
            return render_template('admin/custom_order_form.html', form=form, nuevo=True)

        client = None
        if form.client_id.data and form.client_id.data != 0:
            client = Client.query.get(form.client_id.data)
        if not client:
            if not form.new_client_name.data:
                flash('Debes seleccionar un cliente o ingresar nombre.', 'warning')
                return render_template('admin/custom_order_form.html', form=form, nuevo=True)
            phone_val = (form.new_client_phone.data or '').strip() or 'Sin telefono'
            client = Client(name=form.new_client_name.data.strip(), phone=phone_val)
            db.session.add(client)
            db.session.flush()

        code = generate_custom_order_code()
        while CustomOrder.query.filter_by(code=code).first():
            code = generate_custom_order_code()

        first_item = items_data[0]
        order_measurements = first_item.get('measurements', {})
        order = CustomOrder(
            code=code,
            client_id=client.id,
            garment_type=first_item.get('garment_type'),
            delivery_date=form.delivery_date.data,
            deposit=form.deposit.data,
            total=form.total.data,
            observations=form.observations.data,
            is_urgent=form.is_urgent.data,
            status=form.status.data,
            measurements=order_measurements
        )
        db.session.add(order)
        db.session.flush()

        # Crear prendas asociadas
        for item in items_data:
            item_obj = CustomOrderItem(
                order_id=order.id,
                garment_type=item.get('garment_type'),
                measurements=item.get('measurements', {})
            )
            db.session.add(item_obj)
            # Guardar medidas en el cliente por cada prenda
            m = item.get('measurements', {}) or {}
            if m:
                client.measurements = client.measurements or {}
                client.measurements[item.get('garment_type')] = m

        append_custom_order_history(order, form.status.data, 'Estado inicial', user=current_user.username if current_user.is_authenticated else 'sistema')
        db.session.commit()

        files = request.files.getlist('images')
        saved = save_custom_order_images(files, order)
        for rel in saved:
            db.session.add(CustomOrderImage(filename=rel, order_id=order.id))
        db.session.commit()

        flash('Pedido personalizado creado correctamente.', 'success')
        if 'add_another' in request.form:
            return redirect(url_for('admin_custom_order_nuevo', cliente=client.id))
        return redirect(url_for('admin_custom_order_detalle', order_id=order.id))

    return render_template('admin/custom_order_form.html', form=form, nuevo=True)


@app.route('/admin/pedidos-personalizados/<int:order_id>')
@login_required
def admin_custom_order_detalle(order_id):
    """Detalle de pedido personalizado"""
    pedido = CustomOrder.query.get_or_404(order_id)
    history = get_custom_order_history(pedido)
    return render_template('admin/custom_order_detail.html', pedido=pedido, history=history)


@app.route('/admin/pedidos-personalizados/eliminar/<int:order_id>', methods=['POST'])
@login_required
def admin_custom_order_eliminar(order_id):
    """Eliminar pedido personalizado"""
    pedido = CustomOrder.query.get_or_404(order_id)
    delete_custom_order_assets(pedido)
    code = pedido.code
    db.session.delete(pedido)
    db.session.commit()
    flash(f'Pedido personalizado {code} eliminado.', 'warning')
    return redirect(url_for('admin_custom_orders'))


@app.route('/admin/pedidos-personalizados/<int:order_id>/estado', methods=['POST'])
@login_required
def admin_custom_order_estado(order_id):
    """Actualizar estado del pedido y registrar historial"""
    pedido = CustomOrder.query.get_or_404(order_id)
    new_status = request.form.get('status')
    note = request.form.get('note', '')
    if new_status not in CUSTOM_ORDER_STATUSES:
        abort(400, description='Estado no válido')
    old_status = pedido.status
    pedido.status = new_status
    append_custom_order_history(pedido, new_status, note or f'Cambio desde {old_status}', user=current_user.username)
    db.session.commit()
    flash(f'Estado actualizado a {CUSTOM_ORDER_STATUS_LABELS.get(new_status, new_status)} para {pedido.code}.', 'success')
    return redirect(request.referrer or url_for('admin_custom_orders'))


@app.route('/admin/pedidos-personalizados/<int:order_id>/items/nuevo', methods=['POST'])
@login_required
def admin_custom_order_item_nuevo(order_id):
    """Agregar una nueva prenda dentro del pedido existente"""
    pedido = CustomOrder.query.get_or_404(order_id)
    form = CustomOrderItemForm()
    form.garment_type.choices = [(t, t) for t in CUSTOM_ORDER_TYPES]
    if form.validate_on_submit():
        measures = extract_measurements_from_form(form)
        ref_data = extract_reference_from_form(form)
        measures.update(ref_data)
        item = CustomOrderItem(
            order_id=pedido.id,
            garment_type=form.garment_type.data,
            measurements=measures
        )
        db.session.add(item)
        # Actualizar ultimo tipo/medidas en el cliente para esta prenda
        cliente = pedido.client
        if measures:
            cliente.measurements = cliente.measurements or {}
            cliente.measurements[form.garment_type.data] = measures
        medidas_count = len(measures or {})
        note = f'Prenda agregada: {form.garment_type.data}'
        if medidas_count:
            note += f' ({medidas_count} medidas)'
        append_custom_order_history(pedido, pedido.status, note, user=current_user.username)
        db.session.commit()
        flash('Prenda agregada al pedido.', 'success')
    else:
        flash('No se pudo agregar la prenda, verifica el formulario.', 'danger')
    return redirect(url_for('admin_custom_order_detalle', order_id=pedido.id))


@app.route('/admin/pedidos-personalizados/<int:order_id>/items/<int:item_id>/editar', methods=['POST'])
@login_required
def admin_custom_order_item_editar(order_id, item_id):
    pedido = CustomOrder.query.get_or_404(order_id)
    item = CustomOrderItem.query.get_or_404(item_id)
    if item.order_id != pedido.id:
        abort(404)
    tipo = request.form.get('garment_type')
    if not tipo:
        flash('Tipo de prenda requerido.', 'danger')
        return redirect(url_for('admin_custom_order_detalle', order_id=pedido.id))
    fields = ['largo_espalda','largo_delantero','cintura','busto','media_cintura','sisa','escote','largo_manga','puno','cuello','abertura','ancho_espalda','figura','alforza','panos','wato','corridas','color','cadera','talla','quebrado']
    old_measures = item.measurements or {}
    measures = {}
    for f in fields:
        val = request.form.get(f)
        if val:
            measures[f] = val
    if request.form.get('reference_from_garment'):
        measures['referencia_prenda'] = 'Si'
        note = request.form.get('reference_notes')
        if note:
            measures['nota_referencia'] = note
    item.garment_type = tipo
    item.measurements = measures
    # Registrar cambios de medidas
    changes = []
    keys = set(list(old_measures.keys()) + list(measures.keys()))
    for k in keys:
        old_v = old_measures.get(k)
        new_v = measures.get(k)
        if old_v != new_v:
            changes.append(f"{k}: {old_v or '-'} -> {new_v or '-'}")
    note = f'Prenda editada: {tipo}'
    if changes:
        note += ' | Cambios: ' + '; '.join(changes)
    append_custom_order_history(pedido, pedido.status, note, user=current_user.username)
    db.session.commit()
    flash('Prenda actualizada.', 'success')
    return redirect(url_for('admin_custom_order_detalle', order_id=pedido.id))


@app.route('/admin/pedidos-personalizados/<int:order_id>/items/<int:item_id>/eliminar', methods=['POST'])
@login_required
def admin_custom_order_item_eliminar(order_id, item_id):
    pedido = CustomOrder.query.get_or_404(order_id)
    item = CustomOrderItem.query.get_or_404(item_id)
    if item.order_id != pedido.id:
        abort(404)
    db.session.delete(item)
    append_custom_order_history(pedido, pedido.status, f'Prenda eliminada: {item.garment_type}', user=current_user.username)
    db.session.commit()
    flash('Prenda eliminada del pedido.', 'warning')
    return redirect(url_for('admin_custom_order_detalle', order_id=pedido.id))


@app.route('/admin/pedidos-personalizados/<int:order_id>/editar', methods=['POST'])
@login_required
def admin_custom_order_editar(order_id):
    pedido = CustomOrder.query.get_or_404(order_id)
    old_status = pedido.status
    old_delivery = pedido.delivery_date
    old_deposit = pedido.deposit
    old_total = pedido.total
    old_obs = pedido.observations
    old_urgent = pedido.is_urgent
    delivery_date = request.form.get('delivery_date')
    pedido.delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d').date() if delivery_date else None
    pedido.deposit = request.form.get('deposit') or None
    pedido.total = request.form.get('total') or pedido.total
    pedido.observations = request.form.get('observations')
    pedido.is_urgent = bool(request.form.get('is_urgent'))
    new_status = request.form.get('status') or pedido.status
    pedido.status = new_status
    changes = []
    if old_status != new_status:
        changes.append(f"estado {old_status} -> {new_status}")
    if old_delivery != pedido.delivery_date:
        changes.append(f"entrega {old_delivery or '-'} -> {pedido.delivery_date or '-'}")
    if old_deposit != pedido.deposit:
        changes.append(f"adelanto {old_deposit or 0} -> {pedido.deposit or 0}")
    if old_total != pedido.total:
        changes.append(f"total {old_total or 0} -> {pedido.total or 0}")
    if old_obs != pedido.observations:
        changes.append("observaciones actualizadas")
    if old_urgent != pedido.is_urgent:
        changes.append(f"urgente {old_urgent} -> {pedido.is_urgent}")
    note = f'Pedido editado por {current_user.username}'
    if changes:
        note += " | " + "; ".join(changes)
    append_custom_order_history(pedido, new_status, note, user=current_user.username)
    db.session.commit()
    flash('Pedido actualizado.', 'success')
    return redirect(url_for('admin_custom_order_detalle', order_id=pedido.id))


@app.route('/admin/clientes')
@login_required
def admin_clientes():
    """Listado de clientes"""
    clientes = Client.query.order_by(Client.name).all()
    return render_template('admin/clientes.html', clientes=clientes)


@app.route('/admin/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def admin_cliente_nuevo():
    """Crear cliente y registrar medidas base"""
    form = ClientForm()
    form.garment_type.choices = [(t, t) for t in CUSTOM_ORDER_TYPES]
    if not form.garment_type.data:
        form.garment_type.data = CUSTOM_ORDER_TYPES[0]
    if form.validate_on_submit():
        cliente = Client(name=form.name.data, phone=form.phone.data)
        medidas = extract_measurements_from_form(form)
        if medidas:
            cliente.measurements = {form.garment_type.data: medidas}
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente creado y medidas guardadas.', 'success')
        return redirect(url_for('admin_clientes'))
    
    return render_template('admin/cliente_form.html', form=form, cliente=None, nuevo=True)


@app.route('/admin/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def admin_cliente_editar(id):
    """Editar cliente y medidas"""
    cliente = Client.query.get_or_404(id)
    form = ClientForm()
    form.garment_type.choices = [(t, t) for t in CUSTOM_ORDER_TYPES]
    if request.method == 'GET':
        form.name.data = cliente.name
        form.phone.data = cliente.phone
        form.garment_type.data = CUSTOM_ORDER_TYPES[0]
        # Prefill primeras medidas si existen
        medidas = (cliente.measurements or {}).get(form.garment_type.data, {})
        for k, v in medidas.items():
            if hasattr(form, k):
                getattr(form, k).data = v
    if form.validate_on_submit():
        cliente.name = form.name.data
        cliente.phone = form.phone.data
        medidas = extract_measurements_from_form(form)
        cliente.measurements = cliente.measurements or {}
        if medidas:
            cliente.measurements[form.garment_type.data] = medidas
        db.session.commit()
        flash('Cliente actualizado.', 'success')
        return redirect(url_for('admin_clientes'))
    
    return render_template('admin/cliente_form.html', form=form, cliente=cliente, nuevo=False)


@app.route('/api/clientes/buscar')
@login_required
def api_clientes_buscar():
    """Buscar clientes por nombre o telefono"""
    term = (request.args.get('q') or '').strip()
    if not term:
        return jsonify([])
    like_term = f"%{term}%"
    results = Client.query.filter(
        or_(Client.phone.ilike(like_term), Client.name.ilike(like_term))
    ).order_by(Client.name).limit(8).all()
    data = [{'id': c.id, 'name': c.name, 'phone': c.phone} for c in results]
    return jsonify(data)


@app.route('/api/clientes/<int:client_id>/medidas', methods=['GET', 'POST'])
@login_required
def api_cliente_medidas(client_id):
    """Obtiene o guarda medidas por cliente"""
    cliente = Client.query.get_or_404(client_id)
    if request.method == 'GET':
        prenda = request.args.get('prenda')
        data = (cliente.measurements or {}).get(prenda or '', {}) if prenda else (cliente.measurements or {})
        return jsonify(data)
    
    payload = request.get_json(force=True, silent=True) or {}
    prenda = payload.get('garment_type')
    medidas = payload.get('measurements') or {}
    if not prenda:
        abort(400, description='Falta el tipo de prenda')
    cliente.measurements = cliente.measurements or {}
    cliente.measurements[prenda] = medidas
    db.session.commit()
    return jsonify({'status': 'ok'})


# -------------------------------------------------
#                       MANEJO DE ERRORES
# -------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('El archivo es demasiado grande. Máximo 16MB.', 'danger')
    return redirect(request.referrer or url_for('admin_dashboard'))


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500


# ═══════════════════════════════════════════════════════════════════════════
#                           INICIO
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    with app.app_context():
        init_db()
        print('✓ Base de datos inicializada')
    
    app.run(host='0.0.0.0', port=5000, debug=False)
