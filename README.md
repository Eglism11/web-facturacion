# Sistema de Facturación Web

Sistema de facturación y gestión de cuentas de cobro con Python Flask, PostgreSQL (Supabase) y diseño moderno con Tailwind CSS.

## 🚀 Características

- ✅ Gestión de clientes (CRUD completo)
- ✅ Generación de cuentas de cobro con PDF
- ✅ Dashboard con estadísticas
- ✅ Filtros por estado (pendiente/pagado)
- ✅ Diseño responsive (funciona en móvil)
- ✅ Base de datos PostgreSQL en Supabase
- ✅ Deploy automático en Render.com

## 🛠️ Tecnologías

- **Backend**: Python 3.11 + Flask + SQLAlchemy
- **Base de datos**: PostgreSQL (Supabase)
- **Frontend**: HTML + Tailwind CSS + Alpine.js
- **PDF**: fpdf2
- **Deploy**: Render.com

## 📦 Instalación Local

1. **Clonar y entrar al directorio**:
```bash
cd web-facturacion
```

2. **Crear entorno virtual**:
```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Instalar dependencias**:
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**:
```bash
cp .env.example .env
# Editar .env con tus credenciales de Supabase
```

5. **Inicializar base de datos**:
```bash
python3 -c "from app import app; from models import db; app.app_context().push(); db.create_all()"
```

6. **Ejecutar**:
```bash
python3 app.py
```

Visita: http://localhost:5000

## 🌐 Deploy en Render

### 1. Crear cuenta Supabase

1. Ve a https://supabase.com
2. Crea un nuevo proyecto (gratis)
3. Ve a **Settings** → **Database**
4. Copia la "Connection string" (URI)

### 2. Crear Web Service en Render

1. Ve a https://render.com
2. Crea un **Web Service**
3. Conecta tu repositorio GitHub
4. Selecciona "Python" como entorno
5. Configura:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
6. Agrega variables de entorno:
   - `DATABASE_URL`: Connection string de Supabase
   - `SECRET_KEY`: Genera una clave aleatoria

### 3. Configurar base de datos

En la consola SQL de Supabase, ejecuta:

```sql
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    telefono VARCHAR(50),
    direccion TEXT,
    identificacion VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cuentas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
    concepto TEXT NOT NULL,
    monto DECIMAL(10,2) NOT NULL,
    numero_factura VARCHAR(50) UNIQUE,
    estado VARCHAR(20) DEFAULT 'pendiente',
    pdf_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 📝 Uso

### Dashboard
- Ver estadísticas de facturación
- Acceso rápido a clientes y cuentas

### Clientes
- Crear, editar y eliminar clientes
- Ver historial de cuentas por cliente
- Búsqueda por nombre o email

### Cuentas de Cobro
- Generar nueva cuenta (selecciona cliente, concepto, monto)
- Descargar PDF profesional
- Marcar como pagada
- Filtrar por estado (pendiente/pagado)

## 📄 Estructura del PDF

El PDF generado incluye:
- Número de factura único
- Datos del cliente
- Concepto del servicio
- Monto total
- Fecha de emisión

## 🔒 Seguridad

- La app es pública (sin login)
- Cualquiera con la URL puede crear/ver datos
- Ideal para demo o uso personal controlado
- Para producción con datos sensibles, agregar autenticación

## 💾 Backup

- Supabase incluye backups automáticos
- Puedes exportar datos desde el dashboard de Supabase
- También puedes agregar funcionalidad de exportar CSV

## 🆘 Troubleshooting

**Error: "database does not exist"**
- Verifica que la DATABASE_URL es correcta
- Asegúrate de que el proyecto Supabase esté activo

**Error: "relation does not exist"**
- Las tablas no están creadas
- Ejecuta el SQL de creación de tablas en Supabase

**Error: "Module not found"**
- Asegúrate de instalar requirements.txt
- Verifica que estás en el entorno virtual

## 📧 Contacto

¿Problemas o sugerencias? Crea un issue en el repositorio.

---

Creado con ❤️ usando Flask + Supabase + Tailwind CSS
