from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from config import Config
from models import db, Cliente, Cuenta, Firma, Usuario, CuentaBancaria
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename
import io
import os
import uuid
from PIL import Image

print("[STARTUP] Loading app.py...")
print("[STARTUP] Flask app created")

app = Flask(__name__)
app.config.from_object(Config)

print("[STARTUP] Config loaded, initializing DB...")

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

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
        print(f"Error procesando firma: {e}")
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


app.jinja_env.filters['format_cop_co'] = _jinja_format_cop_co


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
                    nombre VARCHAR(120) NOT NULL,
                    archivo VARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            statements.append("""
                CREATE TABLE firmas (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(120) NOT NULL,
                    archivo VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

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

    if statements:
        with db.engine.begin() as connection:
            for stmt in statements:
                connection.execute(text(stmt))

# Create tables on startup (for development)
with app.app_context():
    db.create_all()
    ensure_schema_updates()
    os.makedirs(SIGNATURE_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(SIGNATURE_PROCESSED_FOLDER, exist_ok=True)
    
    # Create admin user if not exists
    admin_username = Config.ADMIN_USER
    admin_password = Config.ADMIN_PASSWORD
    admin = Usuario.query.filter_by(username=admin_username).first()
    if not admin:
        admin = Usuario(username=admin_username)
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user created: {admin_username}")


# Login Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = Usuario.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        current_user.nombre_completo = request.form.get('nombre_completo', '').strip()
        current_user.cedula = request.form.get('cedula', '').strip()
        db.session.commit()
        login_manager.reload_user()
        flash('Perfil actualizado correctamente', 'success')
        return redirect(url_for('perfil'))
    
    cuentas_bancarias = CuentaBancaria.query.filter_by(usuario_id=current_user.id).all()
    
    firma_actual = None
    firma = Firma.query.filter_by(nombre=f"usuario_{current_user.id}").first()
    if firma:
        firma_actual = firma.archivo  # Base64 string directly
    
    return render_template('perfil.html', usuario=current_user, cuentas_bancarias=cuentas_bancarias, firma_actual=firma_actual)


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
    import re
    
    data = request.get_json()
    if not data or not data.get('firma'):
        return {'success': False, 'error': 'No se recibió imagen'}
    
    firma_data = data['firma']
    header, b64data = firma_data.split(',', 1)
    
    try:
        img_data = base64.b64decode(b64data)
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    from PIL import Image
    import io
    
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
    
    import io
    output = io.BytesIO()
    img.save(output, format='PNG')
    base64_result = f"data:image/png;base64,{base64.b64encode(output.getvalue()).decode('utf-8')}"
    
    firma = Firma.query.filter_by(nombre=f"usuario_{current_user.id}").first()
    if not firma:
        firma = Firma(nombre=f"usuario_{current_user.id}", archivo=base64_result)
        db.session.add(firma)
    else:
        firma.archivo = base64_result
    db.session.commit()
    
    return {'success': True, 'message': 'Firma guardada correctamente', 'base64': base64_result}


@app.route('/perfil/firma/upload', methods=['POST'])
@login_required
def subir_firma_procesada():
    if 'imagen' not in request.files:
        return {'success': False, 'error': 'No se recibió archivo'}
    
    file = request.files['imagen']
    if not file.filename:
        return {'success': False, 'error': 'No hay archivo'}
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_SIGNATURE_EXTENSIONS:
        return {'success': False, 'error': 'Formato no permitido'}
    
    from PIL import Image
    import io
    
    img = Image.open(file)
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
    
    firma = Firma.query.filter_by(nombre=f"usuario_{current_user.id}").first()
    if not firma:
        firma = Firma(nombre=f"usuario_{current_user.id}", archivo=base64_result)
        db.session.add(firma)
    else:
        firma.archivo = base64_result
    db.session.commit()
    
    return {'success': True, 'message': 'Firma procesada correctamente', 'base64': base64_result}

@app.route('/')
@login_required
def index():
    """Dashboard with summary statistics"""
    total_clientes = Cliente.query.count()
    total_cuentas = Cuenta.query.count()

    # Calculate totals
    cuentas = Cuenta.query.all()
    total_facturado = sum(c.monto for c in cuentas)
    total_pendiente = sum(c.monto for c in cuentas if c.estado == 'pendiente')
    total_pagado = sum(c.monto for c in cuentas if c.estado == 'pagado')

    # Recent accounts
    cuentas_recientes = Cuenta.query.order_by(Cuenta.created_at.desc()).limit(5).all()

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

    query = Cliente.query
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
        cliente = Cliente(
            nombre=request.form['nombre'],
            email=request.form.get('email', ''),
            telefono=request.form.get('telefono', ''),
            identificacion=request.form.get('identificacion', '')
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
    cliente = Cliente.query.get_or_404(id)
    cuentas = Cuenta.query.filter_by(cliente_id=id).order_by(Cuenta.created_at.desc()).all()
    return render_template('clientes/detail.html', cliente=cliente, cuentas=cuentas)

@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    """Edit client"""
    cliente = Cliente.query.get_or_404(id)

    if request.method == 'POST':
        cliente.nombre = request.form['nombre']
        cliente.email = request.form.get('email', '')
        cliente.telefono = request.form.get('telefono', '')
        cliente.identificacion = request.form.get('identificacion', '')
        db.session.commit()
        flash('Cliente actualizado', 'success')
        return redirect(url_for('ver_cliente', id=id))

    return render_template('clientes/edit.html', cliente=cliente)

@app.route('/clientes/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_cliente(id):
    """Delete client"""
    cliente = Cliente.query.get_or_404(id)
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

    query = Cuenta.query.join(Cliente)
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
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    firmas = Firma.query.filter_by(nombre=f"usuario_{current_user.id}").all()
    cuentas_bancarias = CuentaBancaria.query.filter_by(usuario_id=current_user.id).order_by(CuentaBancaria.es_principal.desc()).all()
    
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
            firma_usuario = Firma.query.filter_by(nombre=f"usuario_{current_user.id}").first()
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
            db.extract('year', Cuenta.fecha_documento) == year
        ).count() + 1
        numero_factura = f"FAC-{year}-{count:04d}"

        estado = request.form.get('estado', 'pendiente')
        
        cuenta = Cuenta(
            cliente_id=cliente_id,
            concepto=concepto,
            monto=monto,
            numero_factura=numero_factura,
            fecha_documento=fecha_documento,
            firma_id=firma_id,
            numero_cuenta_pago=numero_cuenta_pago,
            estado=estado
        )
        db.session.add(cuenta)
        db.session.commit()

        flash(f'Cuenta de cobro {numero_factura} creada', 'success')
        return redirect(url_for('ver_cuenta', id=cuenta.id))

    return render_template('cuentas/create.html', clientes=clientes, firmas=firmas, today=date.today().isoformat(), perfil=perfil, cuentas_bancarias=cuentas_bancarias)

@app.route('/cuentas/<int:id>')
@login_required
def ver_cuenta(id):
    """View account details"""
    cuenta = Cuenta.query.get_or_404(id)
    return render_template('cuentas/detail.html', cuenta=cuenta)

@app.route('/cuentas/<int:id>/pagar', methods=['POST'])
@login_required
def marcar_pagada(id):
    """Mark account as paid"""
    cuenta = Cuenta.query.get_or_404(id)
    cuenta.estado = 'pagado'
    db.session.commit()
    flash('Cuenta marcada como pagada', 'success')
    return redirect(url_for('ver_cuenta', id=id))

@app.route('/cuentas/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_cuenta(id):
    """Delete account"""
    cuenta = Cuenta.query.get_or_404(id)
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

        firma = Firma(nombre=nombre, archivo=filename)
        db.session.add(firma)
        db.session.commit()
        flash('Firma guardada correctamente.', 'success')
        return redirect(url_for('gestionar_firmas'))

    firmas = Firma.query.order_by(Firma.created_at.desc()).all()
    return render_template('firmas/list.html', firmas=firmas)


@app.route('/firmas/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_firma(id):
    firma = Firma.query.get_or_404(id)
    in_use = Cuenta.query.filter_by(firma_id=id).first()
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
    print(f"[PDF] Generating PDF for account {id}")
    from fpdf import FPDF

    cuenta = Cuenta.query.get_or_404(id)
    cliente = cuenta.cliente
    firma = cuenta.firma

    print(f"[PDF] Cliente: {cliente.nombre}, Firma: {firma}")

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
    prestador_doc = current_user.cedula if current_user.is_authenticated else ''
    prestador_banco = current_user.banco if current_user.is_authenticated else ''
    
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
    pdf.ln(15)

    sig_w_mm = 50
    sig_h_mm = 25
    x_img = pdf.l_margin + (pdf.epw - sig_w_mm) / 2
    if firma:
        firma_path = None
        if firma.archivo.startswith('data:'):
            import tempfile
            header, b64data = firma.archivo.split(',', 1)
            img_data = base64.b64decode(b64data)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp.write(img_data)
                firma_path = tmp.name
        else:
            processed_filename = os.path.splitext(firma.archivo)[0] + '.png'
            firma_path = os.path.join(SIGNATURE_PROCESSED_FOLDER, processed_filename)
        
        if firma_path and os.path.exists(firma_path):
            pdf.image(firma_path, x=x_img, w=sig_w_mm, h=sig_h_mm)
            pdf.ln(3)
            if not firma.archivo.startswith('data:'):
                pass
            else:
                os.remove(firma_path)
        else:
            pdf.ln(8)
    else:
        pdf.ln(8)

    line_y = pdf.get_y()
    line_w = 80
    x_line = pdf.l_margin + (pdf.epw - line_w) / 2
    pdf.line(x_line, line_y, x_line + line_w, line_y)
    pdf.ln(2)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, prestador_nombre or '', align='C', ln=True)

    output = io.BytesIO(pdf.output(dest='S'))

    filename = f"{cuenta.numero_factura}-{cliente.nombre.replace(' ', '_')}.pdf"
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
