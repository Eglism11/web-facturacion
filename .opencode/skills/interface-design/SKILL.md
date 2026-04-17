# Interface Design Skill

Skill especializado en jerarquía visual, recuperación de contenido y consistencia entre dispositivos.

## Protocolos de Diseño (Criterio UI)

### 1. Protocolo de Visibilidad (Anti-Borrado)

- **Color de texto por defecto**: #1F2937 (gris muy oscuro)
- **Queda prohibido**:
  - `display: none` en títulos o párrafos
  - `opacity: 0` en elementos de contenido
- **Contenedores**: Si tienen contenido, usar `height: auto` para evitar colapsos

### 2. Unificación de Jerarquía (Inicio vs. Clientes)

- **Título de sección** debe coincidir con "Clientes":
  - Font-size: 24px (text-2xl)
  - Font-weight: 700 (Bold)
  - Color: #111827
- **Márgenes**:
  - Superior e izquierdo idénticos en todas las páginas
  - Evitar saltos visuales

### 3. Layout de Estadísticas

**Móvil**:
- Grid de 2 columnas estrictas (`grid-cols-2`)
- Tarjetas con fondo blanco (`bg-white`)
- Borde: #E5E7EB (`border-slate-200`)
- border-radius: 12px (`rounded-xl`)

**Desktop**:
- Contenido con `max-width: 1200px` centrado

### 4. Navegación Intuitiva

- **Navbar inferior**: `z-index` alto (`z-50` o superior)
- **Icono activo**: color verde primario (#10b981)

## Checklist de Verificación

Antes de hacer commit, verificar:

- [ ] Títulos visibles con color #1F2937 o #111827
- [ ] Sin `display: none` ni `opacity: 0` en contenido
- [ ] Grid móvil usa `grid-cols-2`
- [ ] Tarjetas tienen `bg-white` y `border-slate-200`
- [ ] Navbar tiene `z-50` mínimo
- [ ] Icono activo usa `text-primary-600`