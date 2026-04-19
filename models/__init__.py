from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre_completo = db.Column(db.String(255))
    cedula = db.Column(db.String(50))
    banco = db.Column(db.String(100))
    numero_cuenta = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cuentas_bancarias = db.relationship('CuentaBancaria', backref='usuario', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if check_password_hash(self.password_hash, password):
            return True
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        if self.password_hash == legacy_hash:
            self.password_hash = generate_password_hash(password)
            return True
        return False

    def __repr__(self):
        return f'<Usuario {self.username}>'

class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.String(36), db.ForeignKey('usuarios.id'), nullable=False)
    nombre = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    telefono = db.Column(db.String(50))
    direccion = db.Column(db.Text)
    identificacion = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    cuentas = db.relationship('Cuenta', backref='cliente', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Cliente {self.nombre}>'

    def to_dict(self):
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'nombre': self.nombre,
            'email': self.email,
            'telefono': self.telefono,
            'direccion': self.direccion,
            'identificacion': self.identificacion,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Cuenta(db.Model):
    __tablename__ = 'cuentas'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.String(36), db.ForeignKey('usuarios.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    concepto = db.Column(db.Text, nullable=False)
    monto = db.Column(db.Numeric(15, 2), nullable=False)
    numero_factura = db.Column(db.String(50), unique=True)
    estado = db.Column(db.String(20), default='pendiente')
    pdf_url = db.Column(db.Text)
    fecha_documento = db.Column(db.Date, default=date.today, nullable=False)
    firma_id = db.Column(db.Integer, db.ForeignKey('firmas.id'))
    numero_cuenta_pago = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Cuenta {self.numero_factura}>'

    def to_dict(self):
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'cliente_id': self.cliente_id,
            'cliente_nombre': self.cliente.nombre if self.cliente else None,
            'concepto': self.concepto,
            'monto': float(self.monto) if self.monto else 0,
            'numero_factura': self.numero_factura,
            'estado': self.estado,
            'fecha_documento': self.fecha_documento.isoformat() if self.fecha_documento else None,
            'firma_nombre': self.firma.nombre if self.firma else None,
            'numero_cuenta_pago': self.numero_cuenta_pago,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CuentaBancaria(db.Model):
    __tablename__ = 'cuentas_bancarias'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.String(36), db.ForeignKey('usuarios.id'), nullable=False)
    nombre_banco = db.Column(db.String(100), nullable=False)
    tipo_cuenta = db.Column(db.String(20), nullable=False)  # Ahorros, Corriente
    numero_cuenta = db.Column(db.String(100), nullable=False)
    es_principal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CuentaBancaria {self.nombre_banco} - {self.numero_cuenta}>'


class Firma(db.Model):
    __tablename__ = 'firmas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    archivo = db.Column(db.Text, nullable=False)  # Base64 string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cuentas = db.relationship('Cuenta', backref='firma', lazy=True)

    def __repr__(self):
        return f'<Firma {self.nombre}>'
