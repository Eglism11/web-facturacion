from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from config import Config
from models import db, Cliente, Cuenta, Firma
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename
import io
import os
import uuid

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

SIGNATURE_UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'firmas')
ALLOWED_SIGNATURE_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def allowed_signature_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_SIGNATURE_EXTENSIONS


def format_cop(value):
    return f"${float(value):,.2f}"


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

    if statements:
        with db.engine.begin() as connection:
            for stmt in statements:
                connection.execute(text(stmt))

# Create tables on startup (for development)
with app.app_context():
    db.create_all()
    ensure_schema_updates()
    os.makedirs(SIGNATURE_UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
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
def ver_cliente(id):
    """View client details"""
    cliente = Cliente.query.get_or_404(id)
    cuentas = Cuenta.query.filter_by(cliente_id=id).order_by(Cuenta.created_at.desc()).all()
    return render_template('clientes/detail.html', cliente=cliente, cuentas=cuentas)

@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
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
def eliminar_cliente(id):
    """Delete client"""
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente eliminado', 'success')
    return redirect(url_for('listar_clientes'))

# Account Routes
@app.route('/cuentas')
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
def crear_cuenta():
    """Create new account"""
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    firmas = Firma.query.order_by(Firma.nombre).all()

    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        concepto = request.form['concepto']
        monto = Decimal(request.form['monto'])
        fecha_documento = datetime.strptime(request.form['fecha_documento'], '%Y-%m-%d').date()
        firma_id = request.form.get('firma_id') or None

        # Generate invoice number
        year = fecha_documento.year
        count = Cuenta.query.filter(
            db.extract('year', Cuenta.fecha_documento) == year
        ).count() + 1
        numero_factura = f"FAC-{year}-{count:04d}"

        cuenta = Cuenta(
            cliente_id=cliente_id,
            concepto=concepto,
            monto=monto,
            numero_factura=numero_factura,
            fecha_documento=fecha_documento,
            firma_id=firma_id,
            estado='pendiente'
        )
        db.session.add(cuenta)
        db.session.commit()

        flash(f'Cuenta de cobro {numero_factura} creada', 'success')
        return redirect(url_for('ver_cuenta', id=cuenta.id))

    return render_template('cuentas/create.html', clientes=clientes, firmas=firmas, today=date.today().isoformat())

@app.route('/cuentas/<int:id>')
def ver_cuenta(id):
    """View account details"""
    cuenta = Cuenta.query.get_or_404(id)
    return render_template('cuentas/detail.html', cuenta=cuenta)

@app.route('/cuentas/<int:id>/pagar', methods=['POST'])
def marcar_pagada(id):
    """Mark account as paid"""
    cuenta = Cuenta.query.get_or_404(id)
    cuenta.estado = 'pagado'
    db.session.commit()
    flash('Cuenta marcada como pagada', 'success')
    return redirect(url_for('ver_cuenta', id=id))

@app.route('/cuentas/<int:id>/eliminar', methods=['POST'])
def eliminar_cuenta(id):
    """Delete account"""
    cuenta = Cuenta.query.get_or_404(id)
    db.session.delete(cuenta)
    db.session.commit()
    flash('Cuenta eliminada', 'success')
    return redirect(url_for('listar_cuentas'))


@app.route('/firmas', methods=['GET', 'POST'])
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

        firma = Firma(nombre=nombre, archivo=filename)
        db.session.add(firma)
        db.session.commit()
        flash('Firma guardada correctamente.', 'success')
        return redirect(url_for('gestionar_firmas'))

    firmas = Firma.query.order_by(Firma.created_at.desc()).all()
    return render_template('firmas/list.html', firmas=firmas)


@app.route('/firmas/<int:id>/eliminar', methods=['POST'])
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
def descargar_pdf(id):
    """Generate and download PDF"""
    from fpdf import FPDF

    cuenta = Cuenta.query.get_or_404(id)
    cliente = cuenta.cliente
    firma = cuenta.firma

    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 12, 15)

    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Fecha: {cuenta.fecha_documento.strftime('%d/%m/%Y')}", ln=True, align='R')
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'DOCUMENTO EQUIVALENTE A LA FACTURA', ln=True, align='C')
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f"Consecutivo: {cuenta.numero_factura}", ln=True, align='R')
    pdf.ln(4)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'Datos del cliente', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Nombre: {cliente.nombre}", ln=True)
    pdf.cell(0, 7, f"NIT/CC: {cliente.identificacion or 'No registrado'}", ln=True)
    pdf.ln(3)

    prestador_nombre = os.environ.get('PRESTADOR_NOMBRE', 'Jesus Briceno')
    prestador_doc = os.environ.get('PRESTADOR_DOCUMENTO', 'CC 0')
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'DEBE A:', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"{prestador_nombre} - {prestador_doc}", ln=True)
    pdf.ln(3)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'Por Concepto de:', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, cuenta.concepto)
    pdf.ln(2)

    monto_texto = numero_a_letras(float(cuenta.monto)).upper()
    pdf.multi_cell(0, 7, f"La suma de: {monto_texto} ({format_cop(cuenta.monto)})")
    pdf.ln(3)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(140, 8, 'Actividad realizada', border=1, align='C')
    pdf.cell(45, 8, 'Total', border=1, align='C', ln=True)
    pdf.set_font('Arial', '', 11)
    concept_x = pdf.get_x()
    concept_y = pdf.get_y()
    pdf.multi_cell(140, 8, cuenta.concepto, border=1)
    concept_end_y = pdf.get_y()
    pdf.set_xy(concept_x + 140, concept_y)
    pdf.cell(45, concept_end_y - concept_y, format_cop(cuenta.monto), border=1, align='R')
    pdf.ln(6)

    banco = os.environ.get('PAGO_BANCO', 'Banco por definir')
    cuenta_pago = os.environ.get('PAGO_CUENTA', 'Cuenta por definir')
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'Informacion de pago', ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Banco: {banco}", ln=True)
    pdf.cell(0, 7, f"Cuenta: {cuenta_pago}", ln=True)
    pdf.ln(3)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 7, 'Informacion adicional', ln=True)
    pdf.set_font('Arial', '', 10)
    texto_tributario = os.environ.get(
        'TEXTO_TRIBUTARIO',
        'No responsable de IVA segun art. 437 del ET. Documento equivalente para soporte contable.'
    )
    pdf.multi_cell(0, 6, texto_tributario)
    pdf.ln(12)

    signature_line_y = pdf.get_y()
    if firma:
        signature_path = os.path.join(SIGNATURE_UPLOAD_FOLDER, firma.archivo)
        if os.path.exists(signature_path):
            pdf.image(signature_path, x=75, y=signature_line_y - 20, w=60)
    pdf.set_y(signature_line_y)
    pdf.line(65, signature_line_y + 10, 145, signature_line_y + 10)
    pdf.set_xy(65, signature_line_y + 12)
    pdf.set_font('Arial', '', 10)
    pdf.cell(80, 6, prestador_nombre, align='C')

    # Output
    output = io.BytesIO(pdf.output(dest='S'))

    filename = f"{cuenta.numero_factura}-{cliente.nombre.replace(' ', '_')}.pdf"
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
