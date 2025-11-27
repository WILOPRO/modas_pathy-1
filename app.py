"""
Modas Pathy - Tienda Virtual
Versión 2.0 - Código refactorizado y optimizado
"""

import os
import re
import random
from datetime import datetime
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
    TextAreaField, SelectField, BooleanField
)
from wtforms.validators import (
    DataRequired, Length, Optional, EqualTo, Regexp, NumberRange
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from sqlalchemy import or_

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
ALLOWED_EXTENSIONS = app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})

for folder in (UPLOAD_FOLDER, PROFILE_FOLDER):
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
        return self.original_price and self.original_price > self.price
    
    @property
    def discount_percent(self):
        """Calcula el porcentaje de descuento"""
        if self.has_discount:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0
    
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


# ═══════════════════════════════════════════════════════════════════════════
#                            FORMULARIOS
# ═══════════════════════════════════════════════════════════════════════════

HEX_COLOR = Regexp(r'^#(?:[0-9a-fA-F]{3}){1,2}$', message='Debe ser un color hex válido')


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión"""
    username = StringField('Usuario', validators=[
        DataRequired(message='El usuario es requerido')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es requerida')
    ])
    remember = BooleanField('Recordarme')
    submit = SubmitField('Ingresar')


class CategoryForm(FlaskForm):
    """Formulario de categoría"""
    name = StringField('Nombre', validators=[
        DataRequired(), Length(max=64)
    ])
    description = TextAreaField('Descripción', validators=[
        Optional(), Length(max=256)
    ])
    icon = StringField('Icono (Bootstrap Icons)', validators=[
        Optional(), Length(max=50)
    ])
    is_active = BooleanField('Activa', default=True)
    submit = SubmitField('Guardar')


class ProductForm(FlaskForm):
    """Formulario de producto"""
    name = StringField('Nombre', validators=[
        DataRequired(), Length(max=128)
    ])
    description = TextAreaField('Descripción', validators=[Optional()])
    price = FloatField('Precio (Bs)', validators=[
        DataRequired(), NumberRange(min=0, message='El precio debe ser positivo')
    ])
    original_price = FloatField('Precio Original (opcional)', validators=[
        Optional(), NumberRange(min=0)
    ])
    category = SelectField('Categoría', coerce=int, validators=[DataRequired()])
    images = MultipleFileField('Imágenes', validators=[
        FileAllowed(ALLOWED_EXTENSIONS, 'Solo imágenes permitidas')
    ])
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
    """Formulario de usuario/administrador"""
    name = StringField('Nombre completo', validators=[
        DataRequired(), Length(max=128)
    ])
    username = StringField('Usuario', validators=[
        DataRequired(), Length(min=3, max=64)
    ])
    password = PasswordField('Contraseña', validators=[Optional(), Length(min=6)])
    password2 = PasswordField('Confirmar Contraseña', validators=[
        Optional(), EqualTo('password', 'Las contraseñas no coinciden')
    ])
    is_superadmin = SelectField('Rol', choices=[
        ('0', 'Administrador'),
        ('1', 'Super Administrador')
    ])
    profile_image = FileField('Foto de perfil', validators=[
        FileAllowed(ALLOWED_EXTENSIONS, 'Solo imágenes permitidas'), Optional()
    ])
    submit = SubmitField('Guardar')


class ProfileForm(FlaskForm):
    """Formulario de edición de perfil"""
    name = StringField('Nombre completo', validators=[
        DataRequired(), Length(max=128)
    ])
    username = StringField('Usuario', validators=[
        DataRequired(), Length(min=3, max=64)
    ])
    password = PasswordField('Nueva Contraseña', validators=[Optional(), Length(min=6)])
    password2 = PasswordField('Confirmar Contraseña', validators=[
        Optional(), EqualTo('password', 'Las contraseñas no coinciden')
    ])
    profile_image = FileField('Foto de perfil', validators=[
        FileAllowed(ALLOWED_EXTENSIONS, 'Solo imágenes permitidas'), Optional()
    ])
    submit = SubmitField('Guardar cambios')


class ThemeForm(FlaskForm):
    """Formulario de tema"""
    name = StringField('Nombre', validators=[DataRequired(), Length(max=50)])
    primary = StringField('Color Primario', validators=[DataRequired(), HEX_COLOR])
    secondary = StringField('Color Secundario', validators=[DataRequired(), HEX_COLOR])
    accent = StringField('Color Acento', validators=[DataRequired(), HEX_COLOR])
    text_color = StringField('Color Texto', validators=[DataRequired(), HEX_COLOR])
    bg_color = StringField('Color Fondo', validators=[DataRequired(), HEX_COLOR])
    success = StringField('Color Éxito', validators=[DataRequired(), HEX_COLOR])
    error = StringField('Color Error', validators=[DataRequired(), HEX_COLOR])
    is_default = BooleanField('Tema por defecto')
    submit = SubmitField('Guardar')


class ContactForm(FlaskForm):
    """Formulario de información de contacto"""
    whatsapp = StringField('WhatsApp', validators=[Optional(), Length(max=20)])
    phone = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Length(max=128)])
    tiktok = StringField('TikTok', validators=[Optional(), Length(max=128)])
    facebook = StringField('Facebook', validators=[Optional(), Length(max=256)])
    instagram = StringField('Instagram', validators=[Optional(), Length(max=128)])
    youtube = StringField('YouTube', validators=[Optional(), Length(max=256)])
    telegram = StringField('Telegram', validators=[Optional(), Length(max=128)])
    address = StringField('Dirección', validators=[Optional(), Length(max=256)])
    city = StringField('Ciudad', validators=[Optional(), Length(max=100)])
    schedule = StringField('Horario', validators=[Optional(), Length(max=256)])
    submit = SubmitField('Guardar')


# ═══════════════════════════════════════════════════════════════════════════
#                        FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════

def slugify(text):
    """Genera un slug URL-friendly a partir de texto"""
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE).strip().lower()
    return re.sub(r'[\s_-]+', '-', text)


def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file, folder, prefix=''):
    """Guarda una imagen y retorna el nombre del archivo"""
    if file and file.filename and allowed_file(file.filename):
        ext = os.path.splitext(file.filename)[1].lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        filename = f"{prefix}{timestamp}{ext}"
        filename = secure_filename(filename)
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return filename
    return None


def create_notification(message, admin_name, type='info'):
    """Crea una notificación en el sistema"""
    notif = Notification(message=message, admin_name=admin_name, type=type)
    db.session.add(notif)
    db.session.commit()


# ═══════════════════════════════════════════════════════════════════════════
#                           DECORADORES
# ═══════════════════════════════════════════════════════════════════════════

def superadmin_required(f):
    """Decorador que requiere permisos de superadministrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            flash('No tienes permisos para acceder a esta sección.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ═══════════════════════════════════════════════════════════════════════════
#                       CONTEXT PROCESSORS
# ═══════════════════════════════════════════════════════════════════════════

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    """Inyecta variables globales en todos los templates"""
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
        'public_categories': categories,
        'contact_info': contact,
        'notifications': notifications,
        'current_year': datetime.utcnow().year,
        'slugify': slugify
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
        producto = Product(
            name=form.name.data,
            slug=slugify(form.name.data),
            description=form.description.data,
            price=form.price.data,
            original_price=form.original_price.data,
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
        producto.name = form.name.data
        producto.slug = slugify(form.name.data)
        producto.description = form.description.data
        producto.price = form.price.data
        producto.original_price = form.original_price.data
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
    
    # Eliminar imágenes
    for img in producto.images.all():
        img_path = os.path.join(UPLOAD_FOLDER, img.filename)
        if os.path.exists(img_path):
            os.remove(img_path)
    
    # Intentar eliminar carpeta
    folder_name = f"{slugify(producto.name)}_{producto.id}"
    product_folder = os.path.join(UPLOAD_FOLDER, folder_name)
    if os.path.exists(product_folder):
        try:
            os.rmdir(product_folder)
        except OSError:
            pass
    
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


# ═══════════════════════════════════════════════════════════════════════════
#                       MANEJO DE ERRORES
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
    
    app.run(host='0.0.0.0', port=5000, debug=True)
