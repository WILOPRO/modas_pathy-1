from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, MultipleFileField, FileField
from wtforms import (
    StringField, PasswordField, SubmitField,
    FloatField, TextAreaField, SelectField,
    BooleanField
)
from wtforms.validators import (
    DataRequired, Length, Optional, EqualTo,
    Regexp
)
from config import Config
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
from datetime import datetime
from sqlalchemy import or_
import random
import os
import re
from flask import Response


app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = 'admin_login'

UPLOAD_FOLDER     = os.path.join('static', 'uploads')
PROFILE_FOLDER    = os.path.join('static', 'perfiles')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

for folder in (UPLOAD_FOLDER, PROFILE_FOLDER):
    os.makedirs(folder, exist_ok=True)


# --- MODELOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=True)
    password = db.Column(db.String(128), nullable=False)
    is_superadmin = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(256), nullable=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref='products')
    is_new       = db.Column(db.Boolean, default=False)
    is_trending  = db.Column(db.Boolean, default=False)
    is_featured  = db.Column(db.Boolean, default=False)

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    is_main = db.Column(db.Boolean, default=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    product = db.relationship('Product', backref='images')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(256), nullable=False)
    admin_name = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Theme(db.Model):
    __tablename__ = 'themes'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(50), unique=True, nullable=False)
    primary    = db.Column(db.String(7), nullable=False)  # e.g. #8F2D56
    secondary  = db.Column(db.String(7), nullable=False)  # e.g. #BF1E53
    accent     = db.Column(db.String(7), nullable=False)  # e.g. #25D366
    text_color = db.Column(db.String(7), nullable=False)  # e.g. #333333
    bg_color   = db.Column(db.String(7), nullable=False)  # e.g. #F8F9FA
    success    = db.Column(db.String(7), nullable=False)  # e.g. #2A9D8F
    error      = db.Column(db.String(7), nullable=False)  # e.g. #E63946
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Theme {self.name}>'
# Información de contacto de la tienda
class ContactInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    whatsapp = db.Column(db.String(128))
    tiktok = db.Column(db.String(128))
    facebook = db.Column(db.String(128))
    gmail = db.Column(db.String(128))
    youtube = db.Column(db.String(128))
    telegram = db.Column(db.String(128))
    address = db.Column(db.String(256))
# --- DECORADOR SUPERADMIN ---
def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_superadmin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# --- FORMULARIOS ---
HEX_COLOR = Regexp(r'^#(?:[0-9a-fA-F]{3}){1,2}$', message="Debe ser un color hex válido")


class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Ingresar')

class CategoryForm(FlaskForm):
    name = StringField('Nombre de categoría', validators=[DataRequired(), Length(max=64)])
    submit = SubmitField('Guardar')

class ProductForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Descripción')
    price = FloatField('Precio (Bs)', validators=[DataRequired()])
    category = SelectField('Categoría', coerce=int, validators=[DataRequired()])
    images = MultipleFileField('Imágenes', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imágenes permitidas')])
    is_new      = BooleanField('Marcar como Novedad')
    is_trending = BooleanField('Marcar como Tendencia')
    is_featured = BooleanField('Marcar como Destacado')
    submit = SubmitField('Guardar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]

class EditProfileForm(FlaskForm):
    name = StringField('Nombre completo', validators=[DataRequired(), Length(max=128)])
    username = StringField('Usuario', validators=[DataRequired(), Length(max=64)])
    password = PasswordField('Nueva Contraseña', validators=[Optional()])
    password2 = PasswordField('Repite la Contraseña', validators=[Optional(), EqualTo('password', 'Las contraseñas no coinciden')])
    profile_image = FileField('Foto de perfil', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imágenes permitidas'), Optional()])
    submit = SubmitField('Guardar cambios')

class UsuarioForm(FlaskForm):
    name = StringField('Nombre completo', validators=[DataRequired(), Length(max=128)])
    username = StringField('Usuario', validators=[DataRequired(), Length(max=64)])
    password = PasswordField('Contraseña (dejar vacío para no cambiar)', validators=[Optional()])
    is_superadmin = SelectField('Tipo', choices=[('0', 'Administrador'), ('1', 'Superadmin')], validators=[DataRequired()])
    profile_image = FileField('Foto de perfil', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'Solo imágenes permitidas'), Optional()])
    submit = SubmitField('Guardar')

class ThemeForm(FlaskForm):
    name       = StringField('Nombre de tema', validators=[DataRequired(), Length(max=50)])
    primary    = StringField('Color primario', validators=[DataRequired(), HEX_COLOR])
    secondary  = StringField('Color secundario', validators=[DataRequired(), HEX_COLOR])
    accent     = StringField('Color acento', validators=[DataRequired(), HEX_COLOR])
    text_color = StringField('Color texto', validators=[DataRequired(), HEX_COLOR])
    bg_color   = StringField('Color fondo', validators=[DataRequired(), HEX_COLOR])
    success    = StringField('Color éxito', validators=[DataRequired(), HEX_COLOR])
    error      = StringField('Color error', validators=[DataRequired(), HEX_COLOR])
    is_default = BooleanField('Tema por defecto')
    submit     = SubmitField('Guardar')
    
class ContactForm(FlaskForm):
    whatsapp = StringField('WhatsApp', validators=[Optional(), Length(max=128)])
    tiktok   = StringField('TikTok', validators=[Optional(), Length(max=128)])
    facebook = StringField('Facebook', validators=[Optional(), Length(max=128)])
    gmail    = StringField('Gmail', validators=[Optional(), Length(max=128)])
    youtube  = StringField('YouTube', validators=[Optional(), Length(max=128)])
    telegram = StringField('Telegram', validators=[Optional(), Length(max=128)])
    address  = StringField('Dirección', validators=[Optional(), Length(max=256)])
    submit   = SubmitField('Guardar')


# --- CONTEXT PROCESSOR para notificaciones globales ---

def _slugify(text):
    t = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE).strip().lower()
    t = re.sub(r'[\s_-]+', '-', t)
    return t

@app.context_processor
def inject_helpers():
    return dict(slugify=_slugify)


    

@app.context_processor
def inject_notifications():
    notifications = Notification.query.order_by(Notification.timestamp.desc()).limit(6).all()
    notifs = [
        {'message': n.message, 'timestamp': n.timestamp.strftime('%d/%m %H:%M'), 'admin_name': n.admin_name}
        for n in notifications
    ]
    return dict(notifications=notifs)



@app.context_processor
def inject_theme():
    active = Theme.query.filter_by(is_default=True).first()
    all_themes = Theme.query.order_by(Theme.name).all()
    return {'active_theme': active, 'all_themes': all_themes}



def seed_themes_once():
    """Crea tablas y siembra temas/contacto solo si aún no existen."""
    db.create_all()

    if Theme.query.count() == 0:
        defaults = [
            ('Light',  '#8F2D56','#BF1E53','#25D366','#333333','#F8F9FA','#2A9D8F','#E63946'),
            ('Dark',   '#333333','#444444','#25D366','#FFFFFF','#222222','#2A9D8F','#E63946'),
            ('Pastel', '#FADADD','#FFC3A0','#BDE0FE','#333333','#FFFFFF','#2A9D8F','#E63946'),
            ('Mono',   '#000000','#444444','#888888','#FFFFFF','#EFEFEF','#2A9D8F','#E63946'),
            ('Sunset', '#FF7E5F','#FEB47B','#FFB85F','#333333','#FFF5E5','#2A9D8F','#E63946'),
        ]
        for i, (n, p, s, a, t, b, u, e) in enumerate(defaults):
            theme = Theme(
                name=n, primary=p, secondary=s, accent=a, text_color=t,
                bg_color=b, success=u, error=e, is_default=(i == 0)
            )
            db.session.add(theme)

        if ContactInfo.query.count() == 0:
            db.session.add(ContactInfo())

        db.session.commit()




# --- RUTAS PÚBLICAS ---


@app.route('/')
def index():
    novedades = Product.query.filter_by(is_new=True).all()
    tendencias = Product.query.filter_by(is_trending=True).all()
    destacados = Product.query.filter_by(is_featured=True).all()
    productos = Product.query.order_by(Product.id.desc()).all()

    # Barajamos cada lista para que salga en orden aleatorio
    random.shuffle(novedades)
    random.shuffle(tendencias)
    random.shuffle(destacados)

    return render_template(
        'public/index.html',
        novedades=novedades,
        tendencias=tendencias,
        destacados=destacados,
        productos=productos
    )



@app.route('/catalogo')
def catalogo():
    q           = request.args.get('q', '', type=str).strip()
    categoria_id= request.args.get('categoria', type=int)
    sort        = request.args.get('sort', 'recientes', type=str)
    page        = request.args.get('page', 1, type=int)
    per_page    = request.args.get('per_page', 12, type=int)

    query = Product.query
    if categoria_id:
        query = query.filter_by(category_id=categoria_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))

    # Orden
    if sort == 'precio_asc':
        query = query.order_by(Product.price.asc(), Product.id.desc())
    elif sort == 'precio_desc':
        query = query.order_by(Product.price.desc(), Product.id.desc())
    elif sort == 'nombre_asc':
        query = query.order_by(Product.name.asc())
    elif sort == 'nombre_desc':
        query = query.order_by(Product.name.desc())
    else:  # recientes
        query = query.order_by(Product.id.desc())

    # Paginación
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    productos  = pagination.items

    categoria = Category.query.get(categoria_id) if categoria_id else None
    categorias = Category.query.order_by(Category.name).all()

    return render_template(
        'public/catalogo.html',
        productos=productos,
        categoria=categoria,
        categorias=categorias,
        search=q,
        sort=sort,
        pagination=pagination,
        per_page=per_page
    )


@app.route('/quienes-somos')
def quienes_somos():
    return render_template('public/quienes_somos.html')

@app.route('/contacto')
def contacto():
    return render_template('public/contacto.html')


@app.route('/p/<slug>-<int:id>')
def producto_seo(slug, id):
    producto = Product.query.get_or_404(id)
    return render_template('public/producto_detalle.html', producto=producto)

# Página de detalle de producto
@app.route('/producto/<int:id>')
def producto_detalle(id):
    producto = Product.query.get_or_404(id)
    return redirect(url_for('producto_seo', id=id, slug=_slugify(producto.name)), code=301)


@app.route('/robots.txt')
def robots_txt():
    from flask import request
    base = request.url_root.rstrip('/')
    content = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    return Response(content, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    from flask import request
    base = request.url_root.rstrip('/')
    static_pages = ['index', 'catalogo', 'quienes_somos', 'contacto']
    urls = []
    for name in static_pages:
        urls.append(f"<url><loc>{base}{url_for(name)}</loc></url>")
    for p in Product.query.order_by(Product.id.desc()).all():
        loc = f"{base}{url_for('producto_seo', id=p.id, slug=_slugify(p.name))}"
        urls.append(f"<url><loc>{loc}</loc></url>")
    xml = "<?xml version='1.0' encoding='UTF-8'?>\n<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>\n" + "\n".join(urls) + "\n</urlset>"
    return Response(xml, mimetype='application/xml')

# --- AUTENTICACIÓN ADMIN ---

@login.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Usuario o contraseña inválidos', 'danger')
            return render_template('admin/login.html', form=form)

        stored = (user.password or "").strip()

        # 1) Intento robusto: probar hash (sea scrypt, pbkdf2, etc.)
        try:
            if stored and (stored.startswith('scrypt:') or stored.startswith('pbkdf2:') or ':' in stored):
                if check_password_hash(stored, password):
                    login_user(user)
                    flash('¡Bienvenido!', 'success')
                    return redirect(url_for('admin_dashboard'))
        except Exception:
            # Si fallara por formato inesperado del hash, seguimos a texto plano
            pass

        # 2) Compatibilidad con contraseñas antiguas en texto plano
        if stored and stored == password:
            user.password = generate_password_hash(password)
            db.session.commit()
            login_user(user)
            flash('¡Bienvenido! (tu contraseña fue actualizada de forma segura)', 'success')
            return redirect(url_for('admin_dashboard'))

        # 3) Error
        flash('Usuario o contraseña inválidos', 'danger')
        return render_template('admin/login.html', form=form)

    return render_template('admin/login.html', form=form)

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

# --- PANEL DE ADMINISTRACIÓN ---
@app.route('/admin')
@login_required
def admin_dashboard():
    productos = Product.query.count()
    categorias = Category.query.count()
    admins = User.query.count()
    return render_template('admin/dashboard.html',
        total_productos=productos,
        total_categorias=categorias,
        total_usuarios=admins
    )

# --- CRUD DE CATEGORÍAS ---
@app.route('/admin/categorias', methods=['GET', 'POST'])
@login_required
def admin_categorias():
    form = CategoryForm()
    if form.validate_on_submit():
        if Category.query.filter_by(name=form.name.data).first():
            flash('Ya existe una categoría con ese nombre.', 'danger')
        else:
            nueva = Category(name=form.name.data)
            db.session.add(nueva)
            db.session.commit()
            flash('Categoría creada', 'success')
            return redirect(url_for('admin_categorias'))
    categorias = Category.query.order_by(Category.id).all()
    return render_template('admin/categorias.html', form=form, categorias=categorias)

@app.route('/admin/categorias/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_categoria_editar(id):
    cat = Category.query.get_or_404(id)
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        cat.name = form.name.data
        db.session.commit()
        flash('Categoría actualizada', 'success')
        return redirect(url_for('admin_categorias'))
    return render_template('admin/categorias_edit.html', form=form, cat=cat)

@app.route('/admin/categorias/eliminar/<int:id>', methods=['POST'])
@login_required
def admin_categoria_eliminar(id):
    cat = Category.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('Categoría eliminada', 'warning')
    return redirect(url_for('admin_categorias'))

# --- CRUD DE PRODUCTOS ---
@app.route('/admin/productos')
@login_required
def admin_productos():
    productos = Product.query.all()
    return render_template('admin/productos.html', productos=productos)

@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
@login_required
def admin_producto_nuevo():
    form = ProductForm()
    if form.validate_on_submit():
        # 1) Crear el producto en DB, incluyendo los flags
        prod = Product(
            name         = form.name.data,
            description  = form.description.data,
            price        = form.price.data,
            category_id  = form.category.data,
            is_new       = form.is_new.data,
            is_trending  = form.is_trending.data,
            is_featured  = form.is_featured.data
        )
        db.session.add(prod)
        db.session.commit()  # <-- prod.id ya disponible

        # 2) Obtener archivos
        files = request.files.getlist('images')

        # 3) Preparar carpeta del producto
        folder_name = secure_filename(prod.name.replace(" ", "_")) + f"_{prod.id}"
        product_folder = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
        os.makedirs(product_folder, exist_ok=True)

        # 4) Índice de la imagen principal
        main_image_index = int(request.form.get("main_image_index", 0))

        # 5) Guardar y renombrar cada archivo
        for i, f in enumerate(files):
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1]
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                new_name = f"{timestamp}_{i}{ext}"
                filename = secure_filename(new_name)
                f.save(os.path.join(product_folder, filename))

                img = ProductImage(
                    filename=os.path.join(folder_name, filename).replace("\\","/"),
                    is_main=(i == main_image_index),
                    product_id=prod.id
                )
                db.session.add(img)

        # 6) Notificación y commit final
        db.session.add(Notification(
            message=f'Se agregó el producto "{prod.name}"',
            admin_name=current_user.username
        ))
        db.session.commit()

        flash('Producto creado correctamente', 'success')
        return redirect(url_for('admin_productos'))

    return render_template('admin/producto_form.html', form=form, nuevo=True, images=[])
@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_producto_editar(id):
    prod = Product.query.get_or_404(id)
    form = ProductForm(obj=prod)
    if form.validate_on_submit():
        # 1) Actualizar datos básicos + flags
        prod.name         = form.name.data
        prod.description  = form.description.data
        prod.price        = form.price.data
        prod.category_id  = form.category.data
        prod.is_new       = form.is_new.data
        prod.is_trending  = form.is_trending.data
        prod.is_featured  = form.is_featured.data

        # 2) Manejo de imágenes igual que antes...
        files = request.files.getlist('images')
        folder_name = secure_filename(prod.name.replace(" ", "_")) + f"_{prod.id}"
        product_folder = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
        os.makedirs(product_folder, exist_ok=True)

        # Eliminar thumbnails marcados
        delete_ids = request.form.getlist('delete_image_ids')
        for img_id in delete_ids:
            img = ProductImage.query.get(int(img_id))
            if img:
                path = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
                if os.path.exists(path):
                    os.remove(path)
                db.session.delete(img)

        # Índice principal
        raw_main = request.form.get("main_image_index", "")
        is_existing = raw_main.startswith("b_")
        main_val = raw_main[2:] if is_existing else raw_main
        try:
            main_int = int(main_val)
        except ValueError:
            main_int = None

        # Marcar existente
        for img in prod.images:
            img.is_main = is_existing and str(img.id) == main_val

        # Guardar nuevas imágenes
        for i, f in enumerate(files):
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1]
                new_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{i}{ext}"
                filename = secure_filename(new_name)
                f.save(os.path.join(product_folder, filename))
                is_main = (not is_existing and i == main_int)
                img = ProductImage(
                    filename=os.path.join(folder_name, filename).replace("\\","/"),
                    is_main=is_main,
                    product_id=prod.id
                )
                db.session.add(img)

        # 3) Notificación y commit
        db.session.add(Notification(
            message=f'Se editó el producto "{prod.name}"',
            admin_name=current_user.username
        ))
        db.session.commit()

        flash('Producto actualizado correctamente', 'success')
        return redirect(url_for('admin_productos'))

    return render_template('admin/producto_form.html', form=form, nuevo=False, images=prod.images)


@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
@login_required
def admin_producto_eliminar(id):
    prod = Product.query.get_or_404(id)
    # Eliminar archivos físicos de todas las imágenes
    for img in prod.images:
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
        if os.path.exists(img_path):
            os.remove(img_path)
    # Eliminar carpeta si está vacía
    folder_name = secure_filename(prod.name.replace(" ", "_")) + f"_{prod.id}"
    product_folder = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    if os.path.exists(product_folder):
        try:
            os.rmdir(product_folder)
        except Exception:
            pass  # Solo borra si está vacía
    db.session.delete(prod)
    db.session.commit()
    db.session.add(Notification(
        message=f'Se eliminó el producto "{prod.name}"',
        admin_name=current_user.username
    ))
    db.session.commit()
    flash('Producto eliminado', 'warning')
    return redirect(url_for('admin_productos'))


# --- PERFIL DE USUARIO ---
@app.route('/admin/profile')
@login_required
def admin_profile():
    return render_template('admin/profile.html', user=current_user)

@app.route('/admin/profile/edit', methods=['GET', 'POST'])
@login_required
def admin_profile_edit():
    form = EditProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.username = form.username.data
        if form.profile_image.data:
            if current_user.profile_image:
                old_path = os.path.join(PROFILE_FOLDER, current_user.profile_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = f"profile_{current_user.id}_{secure_filename(form.profile_image.data.filename)}"
            filepath = os.path.join(PROFILE_FOLDER, filename)
            form.profile_image.data.save(filepath)
            current_user.profile_image = filename
        if form.password.data:
            current_user.password = generate_password_hash(form.password.data)
        db.session.commit()
        flash('Perfil actualizado correctamente', 'success')
        return redirect(url_for('admin_profile'))
    return render_template('admin/profile_edit.html', form=form)

# --- GESTIÓN DE USUARIOS (SOLO SUPERADMIN) ---
@app.route('/admin/usuarios')
@superadmin_required
def admin_usuarios():
    usuarios = User.query.all()
    return render_template('admin/usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/nuevo', methods=['GET', 'POST'])
@superadmin_required
def admin_usuario_nuevo():
    form = UsuarioForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Ya existe un usuario con ese nombre', 'danger')
        else:
            # Validar que venga contraseña al crear (no permitir vacía)
            if not form.password.data:
                flash('Debes especificar una contraseña para el nuevo administrador.', 'danger')
                return render_template('admin/usuario_form.html', form=form, nuevo=True)
            filename = None
            if form.profile_image.data:
                filename = f"profile_{form.username.data}_{secure_filename(form.profile_image.data.filename)}"
                filepath = os.path.join(PROFILE_FOLDER, filename)
                form.profile_image.data.save(filepath)
            user = User(
                username=form.username.data,
                name=form.name.data,
                password=generate_password_hash(form.password.data),
                is_superadmin=(form.is_superadmin.data == '1'),
                profile_image=filename
            )
            db.session.add(user)
            db.session.commit()
            db.session.add(Notification(
                message=f'Se creó el administrador "{user.username}"',
                admin_name=current_user.username
            ))
            db.session.commit()
            flash('Administrador creado correctamente', 'success')
            return redirect(url_for('admin_usuarios'))
    return render_template('admin/usuario_form.html', form=form, nuevo=True)

@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@superadmin_required
def admin_usuario_editar(id):
    user = User.query.get_or_404(id)
    form = UsuarioForm(obj=user)
    form.is_superadmin.data = '1' if user.is_superadmin else '0'
    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data).first()
        if existing and existing.id != user.id:
            flash('Ya existe un usuario con ese nombre', 'danger')
            return render_template('admin/usuario_form.html', form=form, nuevo=False, user=user)
        if form.profile_image.data:
            if user.profile_image:
                old_path = os.path.join(PROFILE_FOLDER, user.profile_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = f"profile_{user.id}_{secure_filename(form.profile_image.data.filename)}"
            filepath = os.path.join(PROFILE_FOLDER, filename)
            form.profile_image.data.save(filepath)
            user.profile_image = filename
        user.name = form.name.data
        user.username = form.username.data
        if form.password.data:
            user.password = generate_password_hash(form.password.data)
        user.is_superadmin = (form.is_superadmin.data == '1')
        db.session.commit()
        db.session.add(Notification(
            message=f'Se editó el administrador "{user.username}"',
            admin_name=current_user.username
        ))
        db.session.commit()
        flash('Usuario actualizado correctamente', 'success')
        return redirect(url_for('admin_usuarios'))
    return render_template('admin/usuario_form.html', form=form, nuevo=False, user=user)

@app.route('/admin/usuarios/eliminar/<int:id>', methods=['POST'])
@superadmin_required
def admin_usuario_eliminar(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('admin_usuarios'))
    if user.profile_image:
        img_path = os.path.join(PROFILE_FOLDER, user.profile_image)
        if os.path.exists(img_path):
            os.remove(img_path)
    db.session.delete(user)
    db.session.commit()
    db.session.add(Notification(
        message=f'Se eliminó el administrador "{user.username}"',
        admin_name=current_user.username
    ))
    db.session.commit()
    flash('Usuario eliminado', 'warning')
    return redirect(url_for('admin_usuarios'))

# --- INFORMACIÓN DE CONTACTO ---
@app.route('/admin/contactos', methods=['GET', 'POST'])
@login_required
def admin_contactos():
    info = ContactInfo.query.first()
    if not info:
        info = ContactInfo()
        db.session.add(info)
        db.session.commit()
    form = ContactForm(obj=info)
    if form.validate_on_submit():
        form.populate_obj(info)
        db.session.commit()
        flash('Datos de contacto actualizados', 'success')
        return redirect(url_for('admin_contactos'))
    return render_template('admin/contactos.html', form=form)

@app.context_processor
def inject_public_data():
    # Traemos categorías para el menú público
    categorias = Category.query.order_by(Category.name).all()
       # Aseguramos que exista un registro de contacto para evitar errores en las
    # vistas públicas
    contact = ContactInfo.query.first()
    if contact is None:
        contact = ContactInfo()
        db.session.add(contact)
        db.session.commit()
    # Exponemos además la hora actual para usar now()
    return {
        'public_categories': categorias,
        'now': lambda fmt=None: datetime.utcnow().strftime(fmt or '%Y'),
        'contact_info': contact
    }

# ─── CRUD DE TEMAS ───────────────────────────────────────────────────────────────

@app.route('/admin/themes')
@login_required
@superadmin_required
def admin_themes():
    temas = Theme.query.order_by(Theme.created_at.desc()).all()
    return render_template('admin/themes.html', temas=temas)

@app.route('/admin/themes/create', methods=['GET','POST'])
@login_required
@superadmin_required
def admin_create_theme():
    form = ThemeForm()
    if form.validate_on_submit():
        if form.is_default.data:
            Theme.query.update({Theme.is_default: False})
        tema = Theme(
            name       = form.name.data,
            primary    = form.primary.data,
            secondary  = form.secondary.data,
            accent     = form.accent.data,
            text_color = form.text_color.data,
            bg_color   = form.bg_color.data,
            success    = form.success.data,
            error      = form.error.data,
            is_default = form.is_default.data
        )
        db.session.add(tema)
        db.session.commit()
        flash('Tema creado con éxito','success')
        return redirect(url_for('admin_themes'))
    return render_template('admin/theme_form.html', form=form, title="Crear Tema")

@app.route('/admin/themes/edit/<int:id>', methods=['GET','POST'])
@login_required
@superadmin_required
def admin_edit_theme(id):
    tema = Theme.query.get_or_404(id)
    form = ThemeForm(obj=tema)
    if form.validate_on_submit():
        if form.is_default.data:
            Theme.query.update({Theme.is_default: False})
        form.populate_obj(tema)
        db.session.commit()
        flash('Tema actualizado','success')
        return redirect(url_for('admin_themes'))
    return render_template('admin/theme_form.html', form=form, title="Editar Tema")

@app.route('/admin/themes/delete/<int:id>', methods=['POST'])
@login_required
@superadmin_required
def admin_delete_theme(id):
    tema = Theme.query.get_or_404(id)
    db.session.delete(tema)
    db.session.commit()
    flash('Tema eliminado','warning')
    return redirect(url_for('admin_themes'))
@app.route('/admin/themes/set', methods=['POST'])
@login_required
@superadmin_required
def admin_set_theme():
    tema_id = request.form.get('theme_id', type=int)
    if tema_id:
        # Desmarca todos
        Theme.query.update({ Theme.is_default: False })
        # Marca el escogido
        elegido = Theme.query.get_or_404(tema_id)
        elegido.is_default = True
        db.session.commit()
        flash(f'Tema cambiado a “{elegido.name}”', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/suscripcion', methods=['GET','POST'])
def suscripcion():
    if request.method == 'POST':
        email = request.form.get('email')
        # aquí podrías guardar ese email en tu base de datos,
        # enviar un mail de confirmación, etc.
        flash('¡Gracias por suscribirte!', 'success')
        return redirect(url_for('index'))
    return render_template('public/suscripcion.html')

# --- MANEJO DE ERRORES -------------------------------------------------------
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('El archivo seleccionado supera el límite permitido.', 'danger')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# --- CREACIÓN DE LA BD Y ARRANQUE ---
if __name__ == '__main__':
    with app.app_context():
        # Crea la base si no existe y siembra datos una sola vez
        seed_themes_once()
    app.run(host='0.0.0.0', port=5000, debug=True)
