from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from models import db, Cliente, Cuenta, Firma, Usuario, CuentaBancaria
from supabase import create_client, Client
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename
import io
import os
import uuid
import base64
from PIL import Image, ImageOps
import logging

print("[STARTUP] Loading app.py...")
print("[STARTUP] Flask app created")

app = Flask(__name__)
app.config.from_object(Config)

@app.errorhandler(500)
def handle_500_error(e):
    import traceback
    error_msg = traceback.format_exc()
    logger.error(f"[ERROR 500] {error_msg}")
    return f"Error interno del servidor: {str(e)}<br><pre>{error_msg}</pre>", 500

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    error_msg = traceback.format_exc()
    logger.error(f"[UNHANDLED EXCEPTION] {error_msg}")
    return f"Error: {str(e)}<br><pre>{error_msg}</pre>", 500

print("[STARTUP] Config loaded, initializing DB...")

db.init_app(app)
csrf = CSRFProtect(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=lambda: generate_csrf())

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

supabase = None

_sb_url = os.environ.get('SUPABASE_URL', Config.SUPABASE_URL)
_sb_key = os.environ.get('SUPABASE_ANON_KEY', Config.SUPABASE_ANON_KEY)

if not _sb_key:
    _sb_key = os.environ.get('SUPABASE_KEY', '')

logger.info(f"[SUPABASE] INIT - URL present: {bool(_sb_url)}, KEY present: {bool(_sb_key)}")
if _sb_key:
    logger.info(f"[SUPABASE] KEY prefix: '{_sb_key[:25]}...'")

if _sb_url and _sb_key:
    try:
        from supabase import create_client
        supabase = create_client(_sb_url, _sb_key)
        logger.info(f"[SUPABASE] Client OK, URL: {_sb_url}")
    except Exception as e:
        logger.error(f"[SUPABASE] FAIL: {e}")
        supabase = None
else:
    logger.warning(f"[SUPABASE] SKIP - URL: '{str(_sb_url)[:30]}', KEY: '{str(_sb_key)[:25]}...'")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'basic'

@login_manager.user_loader
def load_user(user_id):
    try:
        if not user_id:
            return None
        user = Usuario.query.get(str(user_id))
        if user and session.get('user_id') == user.id:
            return user
        return None
    except:
        return None

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email y contraseña son requeridos', 'error')
            return redirect(url_for('login'))

        if supabase:
            try:
                resp = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if resp.user:
                    user = Usuario.query.filter_by(id=resp.user.id).first()
                    if not user:
                        user = Usuario(
                            id=resp.user.id,
                            email=resp.user.email,
                            nombre_completo=resp.user.user_metadata.get('nombre_completo', '')
                        )
                        db.session.add(user)
                        db.session.commit()
                    session['supabase_token'] = resp.session.access_token
                    session['user_id'] = resp.user.id
                    session['email'] = resp.user.email
                    login_user(user)
                    flash('Bienvenido', 'success')
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('index'))
            except Exception as e:
                logger.error(f"[LOGIN] Error: {e}")
                flash('Email o contraseña incorrectos', 'error')
        else:
            user = Usuario.query.filter_by(email=email).first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['email'] = user.email
                login_user(user)
                flash('Bienvenido', 'success')
                return redirect(url_for('index'))
            flash('Email o contraseña incorrectos', 'error')

    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def registro():
    """Registro de nuevos usuarios"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        nombre_completo = request.form.get('nombre_completo', '').strip()

        if not email or not password or not nombre_completo:
            flash('Todos los campos son requeridos', 'error')
            return redirect(url_for('registro'))

        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return redirect(url_for('registro'))

        if password != password_confirm:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('registro'))

        if supabase:
            try:
                resp = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "nombre_completo": nombre_completo
                        }
                    }
                })
                if resp.user:
                    user = Usuario.query.filter_by(id=resp.user.id).first()
                    if not user:
                        user = Usuario(
                            id=resp.user.id,
                            email=resp.user.email,
                            nombre_completo=nombre_completo
                        )
                        db.session.add(user)
                        db.session.commit()
                    session['user_id'] = resp.user.id
                    session['email'] = resp.user.email
                    login_user(user)
                    flash('Cuenta creada exitosamente', 'success')
                    return redirect(url_for('index'))
                elif resp.confirmation_sent:
                    flash('Revisa tu email para confirmar la cuenta', 'success')
                    return redirect(url_for('login'))
            except Exception as e:
                logger.error(f"[REGISTRO] Error: {e}")
                if 'User already registered' in str(e):
                    flash('Este email ya está registrado', 'error')
                else:
                    flash('Error al crear la cuenta. Intenta de nuevo.', 'error')
                return redirect(url_for('registro'))
        else:
            if Usuario.query.filter_by(email=email).first():
                flash('El email ya está registrado', 'error')
                return redirect(url_for('registro'))

            nuevo_usuario = Usuario(
                id=str(uuid.uuid4()),
                email=email,
                nombre_completo=nombre_completo
            )
            nuevo_usuario.set_password(password)
            db.session.add(nuevo_usuario)
            db.session.commit()
            session['user_id'] = nuevo_usuario.id
            session['email'] = nuevo_usuario.email
            login_user(nuevo_usuario)
            flash('Cuenta creada exitosamente', 'success')
            return redirect(url_for('index'))

    return render_template('registro.html')

@app.route('/logout')
@login_required
def logout():
    if supabase and session.get('supabase_token'):
        try:
            supabase.auth.sign_out(session.get('supabase_token'))
        except Exception as e:
            logger.error(f"[LOGOUT] Error: {e}")
    session.clear()
    logout_user()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

@app.route('/recuperar-password', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def recuperar_password():
    """Recuperar contraseña"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        if not email:
            flash('El email es requerido', 'error')
            return redirect(url_for('recuperar_password'))

        logger.info(f"[RECUPERAR] Intentando para {email}, supabase: {supabase is not None}")

        if supabase:
            try:
                supabase.auth.reset_password_for_email(email)
                flash('Revisa tu email para restablecer la contraseña', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                logger.error(f"[RECUPERAR] Error: {e}")
                flash('Error al enviar el email. Verifica el email e intenta de nuevo.', 'error')
        else:
            logger.warning("[RECUPERAR] Supabase no configurado")
            flash('Sistema de recuperación no disponible. Contacta al administrador.', 'error')

    return render_template('recuperar-password.html')

SIGNATURE_UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'firmas')
SIGNATURE_PROCESSED_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'firmas_procesadas')
ALLOWED_SIGNATURE_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def allowed_signature_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_SIGNATURE_EXTENSIONS


def process_signature_remove_background(input_path, output_path):
    """Procesa imagen de firma: convierte fondo blanco/claro a transparente."""
    try:
        img = Image.open(input_path)
        
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        pixels = img.load()
        width, height = img.size
        
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                brightness = (r + g + b) / 3
                if brightness > 230:
                    pixels[x, y] = (r, g, b, 0)
                elif brightness > 200 and a > 100:
                    alpha = int((brightness - 200) / 30 * 255)
                    pixels[x, y] = (r, g, b, min(alpha, a))
        
        img.save(output_path, 'PNG')
        return True
    except Exception as e:
        logger.error(f"[FIRMA] Error procesando firma: {e}")
        return False


def parse_monto_colombia(raw):
    """Acepta '5000000', '5.000.000', '5.000.000,50' y devuelve Decimal."""
    s = (raw or '').strip().replace(' ', '')
    if not s:
        raise ValueError('Monto vacío')
    s = s.replace('.', '')
    if ',' in s:
        s = s.replace(',', '.', 1)
    return Decimal(s)


def format_cop_colombia(value):
    """Formato colombiano: $5.000.000,00"""
    d = Decimal(str(value)).quantize(Decimal('0.01'))
    neg = d < 0
    d = abs(d)
    int_part = int(d)
    resto = d - int_part
    cents = int((resto * 100).to_integral_value())
    int_str = str(int_part)
    chunks = []
    while int_str:
        chunks.append(int_str[-3:])
        int_str = int_str[:-3]
    miles = '.'.join(reversed(chunks)) if chunks else '0'
    sign = '-' if neg else ''
    return f"{sign}${miles},{cents:02d}"


def format_cop(value):
    return format_cop_colombia(value)


def _jinja_format_cop_co(v):
    if v is None:
        return ''
    return format_cop_colombia(v)

def _jinja_format_cop_short(v):
    if v is None:
        return ''
    try:
        val = float(v)
        if val >= 1_000_000_000:
            return f"${val/1_000_000_000:.1f}B"
        elif val >= 1_000_000:
            return f"${val/1_000_000:.1f}M"
        elif val >= 1_000:
            return f"${val/1_000:.0f}K"
        else:
            return format_cop_colombia(v)
    except:
        return format_cop_colombia(v)


app.jinja_env.filters['format_cop_co'] = _jinja_format_cop_co
app.jinja_env.filters['format_cop_short'] = _jinja_format_cop_short


def numero_a_letras(number):
    unidades = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve']
    especiales = {
        10: 'diez', 11: 'once', 12: 'doce', 13: 'trece', 14: 'catorce', 15: 'quince',
        16: 'dieciseis', 17: 'diecisiete', 18: 'dieciocho', 19: 'diecinueve', 20: 'veinte'
    }
    decenas = ['', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa']
    centenas = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos',
                'seiscientos', 'setecientos', 'ochocientos', 'novecientos']

    def convertir_entero(n):
        if n == 0:
            return 'cero'
        if n == 100:
            return 'cien'
        if n <= 20:
            return especiales.get(n, unidades[n])
        if n < 30:
            return 'veinti' + unidades[n - 20]
        if n < 100:
            d, u = divmod(n, 10)
            return decenas[d] if u == 0 else f"{decenas[d]} y {unidades[u]}"
        if n < 1000:
            c, r = divmod(n, 100)
            return centenas[c] if r == 0 else f"{centenas[c]} {convertir_entero(r)}"
        if n < 1_000_000:
            miles, r = divmod(n, 1000)
            miles_txt = 'mil' if miles == 1 else f"{convertir_entero(miles)} mil"
            return miles_txt if r == 0 else f"{miles_txt} {convertir_entero(r)}"
        millones, r = divmod(n, 1_000_000)
        millones_txt = 'un millon' if millones == 1 else f"{convertir_entero(millones)} millones"
        return millones_txt if r == 0 else f"{millones_txt} {convertir_entero(r)}"

    integer_part = int(number)
    decimal_part = int(round((number - integer_part) * 100))
    return f"{convertir_entero(integer_part)} pesos con {decimal_part:02d}/100"


def ensure_schema_updates():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    statements = []

    if 'firmas' not in tables:
        if db.engine.dialect.name == 'sqlite':
            statements.append("""
                CREATE TABLE firmas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id VARCHAR(36) NOT NULL,
                    nombre VARCHAR(120) NOT NULL,
                    archivo TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            statements.append("""
                CREATE TABLE firmas (
                    id SERIAL PRIMARY KEY,
                    usuario_id VARCHAR(36) NOT NULL REFERENCES usuarios(id),
                    nombre VARCHAR(120) NOT NULL,
                    archivo TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        statements.append("CREATE INDEX idx_firmas_usuario_id ON firmas(usuario_id)")
    else:
        firma_columns = {col['name'] for col in inspector.get_columns('firmas')}
        # Skip ALTER for SQLite

    if 'cuentas' in tables:
        cuenta_columns = {col['name'] for col in inspector.get_columns('cuentas')}
        if 'fecha_documento' not in cuenta_columns:
            if db.engine.dialect.name == 'sqlite':
                statements.append("ALTER TABLE cuentas ADD COLUMN fecha_documento DATE")
                statements.append("UPDATE cuentas SET fecha_documento = DATE(created_at) WHERE fecha_documento IS NULL")
            else:
                statements.append("ALTER TABLE cuentas ADD COLUMN fecha_documento DATE")
                statements.append("UPDATE cuentas SET fecha_documento = DATE(created_at) WHERE fecha_documento IS NULL")
                statements.append("ALTER TABLE cuentas ALTER COLUMN fecha_documento SET NOT NULL")

        if 'firma_id' not in cuenta_columns:
            statements.append("ALTER TABLE cuentas ADD COLUMN firma_id INTEGER REFERENCES firmas(id)")

        if 'numero_cuenta_pago' not in cuenta_columns:
            statements.append("ALTER TABLE cuentas ADD COLUMN numero_cuenta_pago VARCHAR(120)")
            
        cuenta_col = inspector.get_columns('cuentas')
        monto_col = next((c for c in cuenta_col if c['name'] == 'monto'), None)
        # Skip SQLite ALTER COLUMN migration

    if statements:
        logger.info(f"[SCHEMA] Running {len(statements)} migrations...")
        for stmt in statements:
            logger.info(f"[SCHEMA] Execute: {stmt[:80]}...")
        with db.engine.begin() as connection:
            for stmt in statements:
                try:
                    connection.execute(text(stmt))
                    logger.info(f"[SCHEMA] Success: {stmt[:50]}...")
                except Exception as e:
                    logger.info(f"[SCHEMA] Skip: {type(e).__name__}")

    # Create tables on startup (for development)
with app.app_context():
    db.create_all()
    ensure_schema_updates()
    os.makedirs(SIGNATURE_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(SIGNATURE_PROCESSED_FOLDER, exist_ok=True)

    # Create admin user if not exists (using email format)
    admin_email = Config.ADMIN_USER
    admin_password = Config.ADMIN_PASSWORD
    admin = Usuario.query.filter_by(email=admin_email).first()
    if not admin:
        admin = Usuario(id=str(uuid.uuid4()), email=admin_email, nombre_completo='Admin')
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        logger.info(f"[STARTUP] Admin user created: {admin_email}")
    else:
        logger.info(f"[STARTUP] Admin user already exists: {admin_email}")


@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    logger.info(f"[PERFIL] Request method: {request.method}, user_id={current_user.id}, email={current_user.email}")
    logger.info(f"[PERFIL] Current nombre_completo BEFORE: '{current_user.nombre_completo}'")
    logger.info(f"[PERFIL] Current cedula BEFORE: '{current_user.cedula}'")
    try:
        if request.method == 'POST':
            nombre = request.form.get('nombre_completo', '').strip()
            cedula = request.form.get('cedula', '').strip()
            logger.info(f"[PERFIL] Form received: nombre='{nombre}', cedula='{cedula}'")
            
            current_user.nombre_completo = nombre
            current_user.cedula = cedula
            
            db.session.commit()
            logger.info(f"[PERFIL] Committed, nombre_completo NOW: '{current_user.nombre_completo}'")
            
            # Refresh to verify
            db.session.refresh(current_user)
            logger.info(f"[PERFIL] After refresh: nombre_completo='{current_user.nombre_completo}', cedula='{current_user.cedula}'")
            
            flash('Perfil actualizado correctamente', 'success')
            return redirect(url_for('perfil'))
        
        cuentas_bancarias = CuentaBancaria.query.filter_by(usuario_id=current_user.id).all()
        
        firma_actual = None
        firma = Firma.query.filter_by(usuario_id=current_user.id).first()
        if firma:
            firma_actual = firma.archivo
            logger.info(f"[PERFIL] Firma found: {firma.id}, length={len(firma.archivo)}")
        
        logger.info(f"[PERFIL] Rendering template with usuario.nombre_completo='{current_user.nombre_completo}'")
        return render_template('perfil.html', usuario=current_user, cuentas_bancarias=cuentas_bancarias, firma_actual=firma_actual)
    except Exception as e:
        import traceback
        logger.info(f"[PERFIL] Error: {traceback.format_exc()}")
        db.session.rollback()
        return f"Error al cargar perfil: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500


@app.route('/perfil/cuenta-bancaria/agregar', methods=['POST'])
@login_required
def agregar_cuenta_bancaria():
    nombre_banco = request.form.get('nombre_banco', '').strip()
    tipo_cuenta = request.form.get('tipo_cuenta', '').strip()
    numero_cuenta = request.form.get('numero_cuenta', '').strip()
    
    if not nombre_banco or not numero_cuenta:
        flash('Todos los campos son requeridos', 'error')
        return redirect(url_for('perfil'))
    
    cuenta = CuentaBancaria(
        usuario_id=current_user.id,
        nombre_banco=nombre_banco,
        tipo_cuenta=tipo_cuenta,
        numero_cuenta=numero_cuenta
    )
    
    existing = CuentaBancaria.query.filter_by(usuario_id=current_user.id).count()
    if existing == 0:
        cuenta.es_principal = True
    
    db.session.add(cuenta)
    db.session.commit()
    flash('Cuenta bancaria agregada', 'success')
    return redirect(url_for('perfil'))


@app.route('/perfil/cuenta-bancaria/<int:id>/principal', methods=['POST'])
@login_required
def set_cuenta_principal(id):
    cuenta = CuentaBancaria.query.get_or_404(id)
    if cuenta.usuario_id != current_user.id:
        flash('No autorizado', 'error')
        return redirect(url_for('perfil'))
    
    CuentaBancaria.query.filter_by(usuario_id=current_user.id).update({'es_principal': False})
    cuenta.es_principal = True
    db.session.commit()
    flash('Cuenta principal actualizada', 'success')
    return redirect(url_for('perfil'))


@app.route('/perfil/cuenta-bancaria/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_cuenta_bancaria(id):
    cuenta = CuentaBancaria.query.get_or_404(id)
    if cuenta.usuario_id != current_user.id:
        flash('No autorizado', 'error')
        return redirect(url_for('perfil'))
    
    db.session.delete(cuenta)
    db.session.commit()
    flash('Cuenta bancaria eliminada', 'success')
    return redirect(url_for('perfil'))


@app.route('/perfil/firma/base64', methods=['POST'])
@login_required
def guardar_firma_base64():
    import base64
    import io
    
    data = request.get_json()
    if not data or not data.get('firma'):
        return jsonify({'success': False, 'error': 'No se recibió imagen'}), 400
    
    firma_data = data['firma']
    header, b64data = firma_data.split(',', 1)
    
    try:
        img_data = base64.b64decode(b64data)
    except Exception as e:
        logger.error(f"[FIRMA] Error decodificando base64: {e}")
        return jsonify({'success': False, 'error': 'Imagen de firma inválida'}), 400
    
    from PIL import Image
    
    img = Image.open(io.BytesIO(img_data))
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    pixels = img.load()
    width, height = img.size
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            brightness = (r + g + b) / 3
            if brightness > 230:
                pixels[x, y] = (r, g, b, 0)
            elif brightness > 200 and a > 100:
                alpha = int((brightness - 200) / 30 * 255)
                pixels[x, y] = (r, g, b, min(alpha, a))
    
    output = io.BytesIO()
    img.save(output, format='PNG')
    base64_result = f"data:image/png;base64,{base64.b64encode(output.getvalue()).decode('utf-8')}"
    
    try:
        firma = Firma.query.filter_by(usuario_id=current_user.id).first()
        if not firma:
            firma = Firma(usuario_id=current_user.id, nombre=f"firma_{current_user.id}", archivo=base64_result)
            db.session.add(firma)
        else:
            firma.archivo = base64_result
        db.session.commit()
        
        logger.info(f"[FIRMA] Guardada: usuario={current_user.id}, firma_id={firma.id}, length={len(base64_result)}, prefix={base64_result[:30]}...")
        return jsonify({'success': True, 'message': 'Firma guardada correctamente', 'base64': base64_result})
    except Exception as e:
        db.session.rollback()
        logger.error(f"[FIRMA] Error guardando firma: {e}")
        return jsonify({'success': False, 'error': 'Error al guardar la firma'}), 500


@app.route('/perfil/firma/upload', methods=['POST'])
@login_required
def subir_firma_procesada():
    import io
    import base64
    from PIL import Image
    
    if 'imagen' not in request.files:
        return jsonify({'success': False, 'error': 'No se recibió archivo'})
    
    file = request.files['imagen']
    if not file.filename:
        return jsonify({'success': False, 'error': 'No hay archivo'})
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_SIGNATURE_EXTENSIONS:
        return jsonify({'success': False, 'error': 'Formato no permitido'})
    
    try:
        img = Image.open(file)
        logger.info(f"[FIRMA_UPLOAD] Original: {img.mode}, size: {img.size}")
        
        # Convert to RGBA
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Create grayscale version
        gray = img.convert('L')
        
        # Resize maintaining aspect
        max_width = 300
        if gray.width > max_width:
            ratio = max_width / gray.width
            new_height = int(gray.height * ratio)
            gray = gray.resize((max_width, new_height), Image.Resampling.LANCZOS)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Create alpha channel from grayscale - white becomes transparent
        alpha = gray.point(lambda x: 255 - x)
        
        # Apply alpha to original
        img.putalpha(alpha)
        
        # Force black signature on transparent background
        pixels = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a > 50:  # If not fully transparent
                    # Make it pure black
                    pixels[x, y] = (0, 0, 0, a)
        
        output = io.BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        
        base64_result = f"data:image/png;base64,{base64.b64encode(output.getvalue()).decode('utf-8')}"
        
        logger.info(f"[FIRMA_UPLOAD] Black on transparent: {len(base64_result)} chars")
        
        firma = Firma.query.filter_by(usuario_id=current_user.id).first()
        if not firma:
            firma = Firma(usuario_id=current_user.id, nombre=f"firma_{current_user.id}", archivo=base64_result)
            db.session.add(firma)
        else:
            firma.archivo = base64_result
        db.session.commit()
        
        logger.info(f"[FIRMA_UPLOAD] OK, firma_id={firma.id}")
        return jsonify({'success': True, 'message': 'Firma guardada', 'base64': base64_result})
    except Exception as e:
        logger.error(f"[FIRMA_UPLOAD] Error procesando firma: {e}")
        return jsonify({'success': False, 'error': 'Error al procesar la imagen'}), 500


@app.route('/perfil/firma/eliminar', methods=['POST'])
@login_required
def eliminar_firma_usuario():
    try:
        firma = Firma.query.filter_by(usuario_id=current_user.id).first()
        if firma:
            db.session.delete(firma)
            db.session.commit()
            logger.info(f"[FIRMA] Eliminada para usuario {current_user.id}")
            return jsonify({'success': True, 'message': 'Firma eliminada'})
        return jsonify({'success': False, 'error': 'No hay firma para eliminar'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"[FIRMA] Error eliminando firma: {e}")
        return jsonify({'success': False, 'error': 'Error al eliminar la firma'}), 500

@app.route('/')
@login_required
def index():
    """Dashboard with summary statistics"""
    total_clientes = Cliente.query.filter_by(usuario_id=current_user.id).count()
    total_cuentas = Cuenta.query.filter_by(usuario_id=current_user.id).count()

    # Calculate totals
    cuentas = Cuenta.query.filter_by(usuario_id=current_user.id).all()
    total_facturado = sum(c.monto for c in cuentas)
    total_pendiente = sum(c.monto for c in cuentas if c.estado == 'pendiente')
    total_pagado = sum(c.monto for c in cuentas if c.estado == 'pagado')

    # Recent accounts
    cuentas_recientes = Cuenta.query.filter_by(usuario_id=current_user.id).order_by(Cuenta.created_at.desc()).limit(5).all()

    return render_template('index.html',
                         total_clientes=total_clientes,
                         total_cuentas=total_cuentas,
                         total_facturado=total_facturado,
                         total_pendiente=total_pendiente,
                         total_pagado=total_pagado,
                         cuentas_recientes=cuentas_recientes)

# Client Routes
@app.route('/clientes')
@login_required
def listar_clientes():
    """List all clients"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')

    query = Cliente.query.filter_by(usuario_id=current_user.id)
    if search:
        query = query.filter(Cliente.nombre.contains(search) | Cliente.email.contains(search))

    clientes = query.order_by(Cliente.nombre).paginate(
        page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False
    )

    return render_template('clientes/list.html', clientes=clientes, search=search)

@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def crear_cliente():
    """Create new client"""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre del cliente es requerido', 'error')
            return redirect(url_for('crear_cliente'))

        cliente = Cliente(
            usuario_id=current_user.id,
            nombre=nombre,
            email=request.form.get('email', '').strip(),
            telefono=request.form.get('telefono', '').strip(),
            identificacion=request.form.get('identificacion', '').strip()
        )
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente creado exitosamente', 'success')
        return redirect(url_for('ver_cliente', id=cliente.id))

    return render_template('clientes/create.html')

@app.route('/clientes/<int:id>')
@login_required
def ver_cliente(id):
    """View client details"""
    cliente = Cliente.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    cuentas = Cuenta.query.filter_by(cliente_id=id, usuario_id=current_user.id).order_by(Cuenta.created_at.desc()).all()
    return render_template('clientes/detail.html', cliente=cliente, cuentas=cuentas)

@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    """Edit client"""
    cliente = Cliente.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash('El nombre del cliente es requerido', 'error')
            return redirect(url_for('editar_cliente', id=id))
        cliente.nombre = nombre
        cliente.email = request.form.get('email', '').strip()
        cliente.telefono = request.form.get('telefono', '').strip()
        cliente.identificacion = request.form.get('identificacion', '').strip()
        db.session.commit()
        flash('Cliente actualizado', 'success')
        return redirect(url_for('ver_cliente', id=id))

    return render_template('clientes/edit.html', cliente=cliente)

@app.route('/clientes/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_cliente(id):
    """Delete client"""
    cliente = Cliente.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente eliminado', 'success')
    return redirect(url_for('listar_clientes'))

# Account Routes
@app.route('/cuentas')
@login_required
def listar_cuentas():
    """List all accounts"""
    page = request.args.get('page', 1, type=int)
    estado = request.args.get('estado', '')

    query = Cuenta.query.filter_by(usuario_id=current_user.id).join(Cliente)
    if estado:
        query = query.filter(Cuenta.estado == estado)

    cuentas = query.order_by(Cuenta.created_at.desc()).paginate(
        page=page, per_page=Config.ITEMS_PER_PAGE, error_out=False
    )

    return render_template('cuentas/list.html', cuentas=cuentas, estado=estado)

@app.route('/cuentas/nueva', methods=['GET', 'POST'])
@login_required
def crear_cuenta():
    """Create new account"""
    try:
        logger.info(f"[CREAR_CUENTA] Starting, user_id={current_user.id}")
        
        clientes = Cliente.query.filter_by(usuario_id=current_user.id).order_by(Cliente.nombre).all()
        logger.info(f"[CREAR_CUENTA] Clientes count: {len(clientes)}")
        
        firmas = Firma.query.filter_by(usuario_id=current_user.id).all()
        logger.info(f"[CREAR_CUENTA] Firmas count: {len(firmas)}")
        
        cuentas_bancarias = CuentaBancaria.query.filter_by(usuario_id=current_user.id).order_by(CuentaBancaria.es_principal.desc()).all()
        logger.info(f"[CREAR_CUENTA] Cuentas bancarias count: {len(cuentas_bancarias)}")
        
        cuenta_principal = next((c for c in cuentas_bancarias if c.es_principal), cuentas_bancarias[0] if cuentas_bancarias else None)
        
        perfil = {
            'banco': cuenta_principal.nombre_banco if cuenta_principal else '',
            'numero_cuenta': cuenta_principal.numero_cuenta if cuenta_principal else ''
        }

        if request.method == 'POST':
            cliente_id = request.form['cliente_id']
            concepto = request.form['concepto']
            try:
                monto = parse_monto_colombia(request.form.get('monto', ''))
            except (ValueError, ArithmeticError):
                flash('El monto no es válido. Usa solo números y separadores (ej: 5.000.000 o 5.000.000,50).', 'error')
                return render_template(
                    'cuentas/create.html',
                    clientes=clientes,
                    firmas=firmas,
                    today=date.today().isoformat(),
                    perfil=perfil,
                    cuentas_bancarias=cuentas_bancarias,
                )
            fecha_documento = datetime.strptime(request.form['fecha_documento'], '%Y-%m-%d').date()
            
            firma_id = request.form.get('firma_id') or None
            if not firma_id:
                firma_usuario = Firma.query.filter_by(usuario_id=current_user.id).first()
                if firma_usuario:
                    firma_id = firma_usuario.id
            
            cuenta_bancaria_id = request.form.get('cuenta_bancaria_id')
            numero_cuenta_pago = ''
            
            if cuenta_bancaria_id:
                cuenta_banc = CuentaBancaria.query.get(cuenta_bancaria_id)
                if cuenta_banc and cuenta_banc.usuario_id == current_user.id:
                    numero_cuenta_pago = f"{cuenta_banc.numero_cuenta} ({cuenta_banc.nombre_banco} - {cuenta_banc.tipo_cuenta})"
            
            if not numero_cuenta_pago:
                numero_cuenta_pago = request.form.get('numero_cuenta_pago', '').strip()
            
            if not numero_cuenta_pago:
                flash('Selecciona una cuenta bancaria o escribe el número manualmente', 'error')
                return render_template(
                    'cuentas/create.html',
                    clientes=clientes,
                    firmas=firmas,
                    today=date.today().isoformat(),
                    perfil=perfil,
                    cuentas_bancarias=cuentas_bancarias,
                )

            year = fecha_documento.year
            count = Cuenta.query.filter(
                db.extract('year', Cuenta.fecha_documento) == year,
                Cuenta.usuario_id == current_user.id
            ).count() + 1
            numero_factura = f"FAC-{year}-{count:04d}"

            cuenta = Cuenta(
                usuario_id=current_user.id,
                cliente_id=cliente_id,
                concepto=concepto,
                monto=monto,
                numero_factura=numero_factura,
                fecha_documento=fecha_documento,
                firma_id=firma_id,
                numero_cuenta_pago=numero_cuenta_pago,
                estado=request.form.get('estado', 'pendiente')
            )
            db.session.add(cuenta)
            db.session.commit()

            flash(f'Cuenta de cobro {numero_factura} creada', 'success')
            return redirect(url_for('ver_cuenta', id=cuenta.id))

        return render_template('cuentas/create.html', clientes=clientes, firmas=firmas, today=date.today().isoformat(), perfil=perfil, cuentas_bancarias=cuentas_bancarias)
    except Exception as e:
        logger.error(f"[CREAR_CUENTA] Error creando cuenta: {e}")
        flash('Error al crear la cuenta. Verifica los datos e intenta de nuevo.', 'error')
        return redirect(url_for('index'))


@app.route('/cuentas/<int:id>')
@login_required
def ver_cuenta(id):
    """View account details"""
    cuenta = Cuenta.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    return render_template('cuentas/detail.html', cuenta=cuenta)

@app.route('/cuentas/<int:id>/pagar', methods=['POST'])
@login_required
def marcar_pagada(id):
    """Mark account as paid"""
    cuenta = Cuenta.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    cuenta.estado = 'pagado'
    db.session.commit()
    flash('Cuenta marcada como pagada', 'success')
    return redirect(url_for('ver_cuenta', id=id))

@app.route('/cuentas/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_cuenta(id):
    """Delete account"""
    cuenta = Cuenta.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(cuenta)
    db.session.commit()
    flash('Cuenta eliminada', 'success')
    return redirect(url_for('listar_cuentas'))


@app.route('/firmas', methods=['GET', 'POST'])
@login_required
def gestionar_firmas():
    """Upload and manage signatures"""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        archivo = request.files.get('archivo')

        if not nombre:
            flash('Debes indicar un nombre para la firma.', 'error')
            return redirect(url_for('gestionar_firmas'))

        if not archivo or not archivo.filename:
            flash('Debes seleccionar una imagen de firma.', 'error')
            return redirect(url_for('gestionar_firmas'))

        if not allowed_signature_file(archivo.filename):
            flash('Formato no permitido. Usa PNG o JPG.', 'error')
            return redirect(url_for('gestionar_firmas'))

        extension = archivo.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{uuid.uuid4().hex}.{extension}")
        save_path = os.path.join(SIGNATURE_UPLOAD_FOLDER, filename)
        archivo.save(save_path)

        processed_filename = os.path.splitext(filename)[0] + '.png'
        processed_path = os.path.join(SIGNATURE_PROCESSED_FOLDER, processed_filename)
        process_signature_remove_background(save_path, processed_path)

        try:
            with open(processed_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            base64_result = f"data:image/png;base64,{img_data}"
        except Exception as e:
            logger.error(f"[FIRMA] Error convirtiendo imagen a base64: {e}")
            flash('Error al procesar la imagen', 'error')
            return redirect(url_for('gestionar_firmas'))

        firma = Firma(usuario_id=current_user.id, nombre=nombre, archivo=base64_result)
        db.session.add(firma)
        db.session.commit()
        os.remove(save_path)
        os.remove(processed_path)
        flash('Firma guardada correctamente.', 'success')
        return redirect(url_for('gestionar_firmas'))

    firmas = Firma.query.filter_by(usuario_id=current_user.id).order_by(Firma.created_at.desc()).all()
    return render_template('firmas/list.html', firmas=firmas)


@app.route('/firmas/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_firma(id):
    firma = Firma.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    in_use = Cuenta.query.filter_by(firma_id=id, usuario_id=current_user.id).first()
    if in_use:
        flash('No se puede eliminar la firma porque ya esta asociada a una cuenta.', 'error')
        return redirect(url_for('gestionar_firmas'))

    file_path = os.path.join(SIGNATURE_UPLOAD_FOLDER, firma.archivo)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(firma)
    db.session.commit()
    flash('Firma eliminada.', 'success')
    return redirect(url_for('gestionar_firmas'))

@app.route('/cuentas/<int:id>/pdf')
@login_required
def descargar_pdf(id):
    """Generate and download equivalent invoice PDF"""
    logger.info(f"[PDF] Generating PDF for account {id}")
    from fpdf import FPDF

    cuenta = Cuenta.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    cliente = cuenta.cliente
    firma = cuenta.firma
    
    # Debug: Show firma details
    logger.info(f"[PDF] Cuenta: {cuenta.numero_factura}, cliente: {cliente.nombre}")
    logger.info(f"[PDF] Cuenta.firma_id: {cuenta.firma_id}")
    logger.info(f"[PDF] Firma from cuenta.firma: {firma}")
    
    # If no firma on account, try to get user's default firma
    if not firma:
        firma_usuario = Firma.query.filter_by(usuario_id=current_user.id).first()
        if firma_usuario:
            firma = firma_usuario
            logger.info(f"[PDF] Using user's default firma: id={firma.id}")
        else:
            logger.info(f"[PDF] No firma found for account or user")
    
    if firma:
        logger.info(f"[PDF] Firma found: id={firma.id}, archivo type={type(firma.archivo)}, starts_with='{firma.archivo[:30] if firma.archivo else 'empty'}'")
    else:
        logger.info(f"[PDF] No firma to display")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 12, 15)

    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Fecha: {cuenta.fecha_documento.strftime('%d/%m/%Y')}", ln=True, align='L')
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'DOCUMENTO EQUIVALENTE A LA FACTURA', ln=True, align='C')
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Consecutivo: {cuenta.numero_factura}", ln=True, align='R')
    pdf.ln(6)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Datos del cliente', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Nombre: {cliente.nombre}", ln=True)
    pdf.cell(0, 7, f"NIT/CC: {cliente.identificacion or 'No registrado'}", ln=True)
    pdf.ln(5)

    prestador_nombre = current_user.nombre_completo if current_user.is_authenticated else ''
    if not prestador_nombre:
        prestador_nombre = os.environ.get('PRESTADOR_NOMBRE', '')
    prestador_doc = current_user.cedula if current_user.is_authenticated else ''
    prestador_banco = current_user.banco if current_user.is_authenticated else ''
    if not prestador_banco:
        prestador_banco = os.environ.get('PAGO_BANCO', '')
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'DEBE A:', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Nombre completo: {prestador_nombre or '(Configure su perfil)'}", ln=True)
    pdf.cell(0, 7, f"Cedula/CE: {prestador_doc or '(Configure su perfil)'}", ln=True)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Por Concepto de:', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, cuenta.concepto)
    pdf.ln(3)

    monto_formatted = format_cop(cuenta.monto)
    monto_texto = numero_a_letras(float(cuenta.monto)).upper()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'La suma de:', ln=True)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, f"{monto_texto} ({monto_formatted})", ln=True)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(140, 10, 'Actividad realizada', border=1, align='C')
    pdf.cell(45, 10, 'Total', border=1, align='C', ln=True)
    pdf.set_font('Arial', '', 10)
    concept_x = pdf.get_x()
    concept_y = pdf.get_y()
    pdf.multi_cell(140, 10, cuenta.concepto, border=1)
    concept_end_y = pdf.get_y()
    pdf.set_xy(concept_x + 140, concept_y)
    pdf.cell(45, concept_end_y - concept_y, monto_formatted, border=1, align='R')
    pdf.ln(10)

    numero_pago = (getattr(cuenta, 'numero_cuenta_pago', None) or '').strip()
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, 'Informacion de pago', ln=True)
    pdf.set_font('Arial', '', 11)
    banco_info = f"({prestador_banco})" if prestador_banco else ""
    linea_pago = f"El pago debera efectuarse a: {numero_pago or '—'} {banco_info} a nombre de {prestador_nombre or 'el prestador'}"
    pdf.multi_cell(0, 7, linea_pago)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, 'Informacion adicional', ln=True)
    pdf.set_font('Arial', '', 10)
    texto_tributario = os.environ.get(
        'TEXTO_TRIBUTARIO',
        'No responsable de IVA segun art. 437 del ET. Documento equivalente para soporte contable.'
    )
    pdf.multi_cell(0, 6, texto_tributario)
    pdf.ln(8)

    sig_w_mm = 40
    sig_h_mm = 12
    x_img = pdf.l_margin + (pdf.epw - sig_w_mm) / 2
    
    logger.info(f"[PDF] Adding signature, firma={firma}")
    
    if firma and firma.archivo:
        if firma.archivo.startswith('data:'):
            try:
                import tempfile
                header, b64data = firma.archivo.split(',', 1)
                img_data = base64.b64decode(b64data)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(img_data)
                    firma_path = tmp.name
                
                logger.info(f"[PDF] Signature temp file: {firma_path}, size: {os.path.getsize(firma_path)}")
                
                if os.path.exists(firma_path) and os.path.getsize(firma_path) > 0:
                    pdf.image(firma_path, x=x_img, w=sig_w_mm, h=sig_h_mm)
                    pdf.ln(1)
                    os.remove(firma_path)
                    print("[PDF] Signature added successfully")
                else:
                    print("[PDF] Temp file invalid or empty")
                    pdf.ln(3)
            except Exception as pdf_err:
                logger.info(f"[PDF] Error adding signature: {pdf_err}")
                pdf.ln(3)
        else:
            processed_filename = os.path.splitext(firma.archivo)[0] + '.png'
            firma_path = os.path.join(SIGNATURE_PROCESSED_FOLDER, processed_filename)
            if os.path.exists(firma_path):
                pdf.image(firma_path, x=x_img, w=sig_w_mm, h=sig_h_mm)
                pdf.ln(1)
            else:
                logger.info(f"[PDF] Signature file not found: {firma_path}")
                pdf.ln(3)
    else:
        print("[PDF] No firma to display")
        pdf.ln(3)

    line_y = pdf.get_y()
    line_w = 60
    x_line = pdf.l_margin + (pdf.epw - line_w) / 2
    pdf.line(x_line, line_y, x_line + line_w, line_y)
    pdf.ln(1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 4, prestador_nombre or '', align='C', ln=True)

    output = io.BytesIO(pdf.output(dest='S'))

    filename = f"{cuenta.numero_factura}-{cliente.nombre.replace(' ', '_')}.pdf"
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
