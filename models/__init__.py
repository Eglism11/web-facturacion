from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from flask_login import UserMixin
import hashlib

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    nombre_completo = db.Column(db.String(255))
    cedula = db.Column(db.String(50))
    banco = db.Column(db.String(100))
    numero_cuenta = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    def __repr__(self):
        return f'<Usuario {self.username}>'

class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
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
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    concepto = db.Column(db.Text, nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
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


class Firma(db.Model):
    __tablename__ = 'firmas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    archivo = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cuentas = db.relationship('Cuenta', backref='firma', lazy=True)

    def __repr__(self):
        return f'<Firma {self.nombre}>'
