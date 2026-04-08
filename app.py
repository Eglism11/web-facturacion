from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from config import Config
from models import db, Cliente, Cuenta
from datetime import datetime
import io

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# Create tables on startup (for development)
with app.app_context():
    db.create_all()

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
            direccion=request.form.get('direccion', ''),
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
        cliente.direccion = request.form.get('direccion', '')
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

    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        concepto = request.form['concepto']
        monto = float(request.form['monto'])

        # Generate invoice number
        year = datetime.now().year
        count = Cuenta.query.filter(
            db.extract('year', Cuenta.created_at) == year
        ).count() + 1
        numero_factura = f"FAC-{year}-{count:04d}"

        cuenta = Cuenta(
            cliente_id=cliente_id,
            concepto=concepto,
            monto=monto,
            numero_factura=numero_factura,
            estado='pendiente'
        )
        db.session.add(cuenta)
        db.session.commit()

        flash(f'Cuenta de cobro {numero_factura} creada', 'success')
        return redirect(url_for('ver_cuenta', id=cuenta.id))

    return render_template('cuentas/create.html', clientes=clientes)

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

@app.route('/cuentas/<int:id>/pdf')
def descargar_pdf(id):
    """Generate and download PDF"""
    from fpdf import FPDF

    cuenta = Cuenta.query.get_or_404(id)
    cliente = cuenta.cliente

    # Create PDF
    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 20, 'CUENTA DE COBRO', align='C', ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Invoice info
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 8, f"Factura #: {cuenta.numero_factura}", ln=False)
    pdf.cell(95, 8, f"Fecha: {cuenta.created_at.strftime('%d/%m/%Y')}", ln=True, align='R')
    pdf.ln(5)

    # Client info
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, ' CLIENTE', ln=True, fill=True)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f"  {cliente.nombre}", ln=True)
    if cliente.email:
        pdf.cell(0, 6, f"  Email: {cliente.email}", ln=True)
    if cliente.telefono:
        pdf.cell(0, 6, f"  Teléfono: {cliente.telefono}", ln=True)
    pdf.ln(10)

    # Concept table
    pdf.set_fill_color(60, 60, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(140, 10, ' Concepto', ln=False, fill=True)
    pdf.cell(50, 10, 'Monto', ln=True, fill=True, align='R')

    pdf.set_fill_color(245, 245, 245)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font('Arial', '', 10)
    pdf.cell(140, 12, f' {cuenta.concepto}', ln=False, fill=True)
    pdf.cell(50, 12, f'${cuenta.monto:,.2f}', ln=True, fill=True, align='R')
    pdf.ln(5)

    # Total
    pdf.line(120, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, 'TOTAL:', ln=False, align='R')
    pdf.cell(50, 10, f'${cuenta.monto:,.2f}', ln=True, align='R')

    # Output
    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)

    filename = f"{cuenta.numero_factura}-{cliente.nombre.replace(' ', '_')}.pdf"
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
